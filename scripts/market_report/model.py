"""Assemble one trading day's dataset from every source, with graceful degradation."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from . import bot as bot_mod
from . import cis as cis_mod
from .dse import CROSS_LISTED, DSE, INDEX_NAMES, INDEX_ORDER, parse_report
from .util import Http, iso, now_eat, num, parse_iso, pct_change

TENORS = [2, 5, 7, 10, 15, 20, 25]
HISTORY_DAYS = 30  # trading days kept for the trend tiles


def _sum(rows, key):
    return sum((r.get(key) or 0.0) for r in rows)


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text())
    except Exception:  # noqa: BLE001
        return default


def save_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, default=str, ensure_ascii=False))


class Builder:
    def __init__(self, data_dir: Path, http: Http | None = None, log=print):
        self.data_dir = data_dir
        self.http = http or Http()
        self.dse = DSE(self.http)
        self.log = log
        self.notes: list[str] = []  # anything that degraded, surfaced in the report footer

    # ── helpers ─────────────────────────────────────────────────────
    def year_start_prices(self, year: int, rows: list[dict]) -> dict[str, float | None]:
        """Last close of the previous year per counter, adjusted for share splits.

        The feed does not restate history after a split (NMB's 10-for-1 in 2026 left its
        31 Dec 2025 close at 8,410 against a post-split price of ~2,000), so when the shares in
        issue have changed by a clean integer ratio we scale the old price by the same ratio."""
        path = self.data_dir / "year_start_prices.json"
        store = load_json(path, {})
        ys = store.setdefault(str(year), {})
        changed = False
        for r in rows:
            c = r["code"]
            if c not in ys or not isinstance(ys[c], dict):
                try:
                    got = self.dse.closing_price_on_or_before(c, date(year - 1, 12, 31))
                    ys[c] = {"price": got[0], "date": got[1], "shares": got[2]} if got else {"price": None}
                    changed = True
                except Exception as e:  # noqa: BLE001
                    self.log(f"year-start price {c}: {e}")
        if changed:
            save_json(path, store)
        out = {}
        for r in rows:
            rec = ys.get(r["code"]) or {}
            price, then, now = rec.get("price"), rec.get("shares"), r.get("shares_in_issue")
            if not price:
                out[r["code"]] = None
                continue
            raw_ytd = abs(((r.get("close") or 0) / price - 1) * 100) if r.get("close") else 0
            shares_moved = bool(then and now and abs(then / now - 1) > 0.02)
            today = iso(date.today())
            if (shares_moved or raw_ytd > 60) and rec.get("split_checked") != today:
                try:
                    rec["split_factor"] = self._split_factor(r["code"], date(year - 1, 12, 31), then, now)
                except Exception as e:  # noqa: BLE001
                    self.log(f"split check {r['code']}: {e}")
                    rec.setdefault("split_factor", 1.0)
                rec["split_checked"] = today
                ys[r["code"]] = rec
                changed = True
            f = rec.get("split_factor") or 1.0
            if f != 1.0:
                self.notes.append(f"{r['code']}: year-start price adjusted for a {f:g}-for-1 share split.")
            out[r["code"]] = price / f
        if changed:
            save_json(path, store)
        return out

    def _split_factor(self, code: str, since: date, shares_then, shares_now) -> float:
        """A genuine split shows as a one-day price step of ~n× AND more shares in issue now than at
        the year start (a rights or bonus issue changes the share count without the price step;
        an illiquid counter can jump in price without any change in shares). The feed's daily
        share counts flicker, so the share test uses the year-start and current figures only."""
        rows = [r for r in self.dse.price_series(code, 400) if r["date"] > iso(since) and r["close"]]
        more_shares = bool(shares_then and shares_now and shares_now > shares_then * 1.5)
        fewer_shares = bool(shares_then and shares_now and shares_then > shares_now * 1.5)
        factor = 1.0
        for a, b in zip(rows, rows[1:]):
            ratio = a["close"] / b["close"] if b["close"] else 0
            if ratio >= 1.7 and more_shares:  # price fell to roughly 1/n
                n = round(ratio)
                if n >= 2 and abs(ratio - n) / n <= 0.2:
                    factor *= n
            elif 0 < ratio <= 1 / 1.7 and fewer_shares:  # consolidation: price rose n×
                n = round(1 / ratio)
                if n >= 2 and abs(1 / ratio - n) / n <= 0.2:
                    factor /= n
        return factor

    def previous_trading_day(self, d: date) -> tuple[date, list[dict]]:
        """Walk back until the API returns rows actually dated before d."""
        probe = d - timedelta(days=1)
        for _ in range(10):
            rows = self.dse.equities(probe)
            if rows:
                td = parse_iso(rows[0]["trade_date"]) if rows[0].get("trade_date") else probe
                if td < d:
                    return td, rows
                probe = td - timedelta(days=1)
                continue
            probe -= timedelta(days=1)
        raise RuntimeError("could not find a previous trading day")

    # ── main ───────────────────────────────────────────────────────
    def build(self, d: date, prev_loader=None) -> dict:
        """prev_loader(prev_date) -> the previous day's saved dataset (or None)."""
        log = self.log
        log(f"building dataset for {iso(d)}")

        eq_api = self.dse.equities(d)
        if not eq_api or parse_iso(eq_api[0]["trade_date"]) != d:
            raise RuntimeError(f"DSE has no equity data dated {iso(d)} yet")
        prev_d, eq_prev = self.previous_trading_day(d)
        log(f"previous trading day {iso(prev_d)}")
        prev_snapshot = prev_loader(prev_d) if prev_loader else None

        # indices (API) today / previous
        idx_today = {r["code"]: r for r in self.dse.indices(d)}
        try:
            idx_prev = {r["code"]: r for r in self.dse.indices(prev_d)}
        except Exception as e:  # noqa: BLE001
            idx_prev = {}
            self.notes.append(f"previous-day indices unavailable ({e})")

        # per-security deals (API) – fallback when the exchange report is late
        try:
            summ = {r["code"]: r for r in self.dse.daily_summary(d)}
        except Exception as e:  # noqa: BLE001
            summ = {}
            self.notes.append(f"daily summary unavailable ({e})")

        # the exchange's own report (richest source)
        report, report_url = None, None
        try:
            links = self.dse.daily_report_links()
            for rd, url in links:
                if rd == d:
                    report_url = url
                    break
            if report_url is None and links and links[0][0] is None:
                # dates not readable – try the newest links until one matches
                for rd, url in links[:3]:
                    pages = self.dse.fetch_report_lines(url)
                    cand = parse_report(pages)
                    if cand.get("report_date") == d:
                        report, report_url = cand, url
                        break
            elif report_url:
                report = parse_report(self.dse.fetch_report_lines(report_url))
                if report.get("report_date") not in (None, d):
                    self.notes.append("exchange report date did not match; ignored")
                    report = None
        except Exception as e:  # noqa: BLE001
            self.notes.append(f"exchange Market Report could not be read ({e})")
        if report is None:
            self.notes.append("The DSE Market Report for this day was not yet published when this page was built; "
                              "foreign-participation, bond-trade and bid/offer details will be filled in on the next run.")
        else:
            log(f"exchange report parsed: {len(report['equities']['rows'])} equity rows, "
                f"{len(report['bond_trades']['rows'])} bond trades")

        # ── equities table ────────────────────────────────────────
        rep_rows = {r["code"]: r for r in (report or {}).get("equities", {}).get("rows", [])}
        api_codes = {r["code"] for r in eq_api}
        for code, rr in rep_rows.items():  # suspended/untraded counters the price feed omits
            if code not in api_codes:
                eq_api.append({"code": code, "trade_date": iso(d), "open": rr["prev_close"], "close": rr["close"],
                               "high": rr["high"], "low": rr["low"], "prev_close": rr["prev_close"], "change_pct": None,
                               "turnover": rr["turnover"], "volume": rr["volume"], "shares_in_issue": None,
                               "market_cap": (rr["market_cap_bn"] or 0.0) * 1e9, "from_report": True})
        year = d.year
        ys = self.year_start_prices(year, eq_api)
        prev_map = {r["code"]: r for r in eq_prev}
        # when there is no saved snapshot for the previous day, read the exchange's report for it
        prev_report = None
        if prev_snapshot is None:
            try:
                for rd, url in self.dse.daily_report_links():
                    if rd == prev_d:
                        prev_report = parse_report(self.dse.fetch_report_lines(url))
                        log("previous-day exchange report parsed for comparisons")
                        break
            except Exception as e:  # noqa: BLE001
                self.notes.append(f"previous-day exchange report not read ({e})")
        equities = []
        for r in sorted(eq_api, key=lambda x: x["code"]):
            rr = rep_rows.get(r["code"], {})
            close, prev_close = r["close"], r["prev_close"]
            if prev_close in (None, 0) and prev_map.get(r["code"]):
                prev_close = prev_map[r["code"]]["close"]
            ystart = ys.get(r["code"])
            deals = rr.get("deals") if rr else summ.get(r["code"], {}).get("trades")  # None when unknown
            equities.append({
                "code": r["code"], "cross_listed": r["code"] in CROSS_LISTED,
                "prev_close": prev_close, "close": close, "high": r["high"], "low": r["low"],
                "change_pct": pct_change(close, prev_close),
                "year_start": ystart, "ytd_pct": pct_change(close, ystart),
                "turnover": rr.get("turnover", r["turnover"]) or 0.0,
                "deals": deals, "volume": rr.get("volume", r["volume"]) or 0.0,
                "market_cap_bn": (r["market_cap"] or 0.0) / 1e9,
                "bids": rr.get("bids"), "offers": rr.get("offers"),
                "shares_in_issue": r["shares_in_issue"],
            })
        tot = {"turnover": _sum(equities, "turnover"), "deals": sum(int(e["deals"] or 0) for e in equities) if report else None,
               "volume": _sum(equities, "volume"), "market_cap_bn": _sum(equities, "market_cap_bn"),
               "domestic_cap_bn": sum(e["market_cap_bn"] for e in equities if not e["cross_listed"]),
               "bids": _sum(equities, "bids") if report else None, "offers": _sum(equities, "offers") if report else None}
        prev_tot = {"turnover": _sum(eq_prev, "turnover"), "volume": _sum(eq_prev, "volume"),
                    "market_cap_bn": _sum(eq_prev, "market_cap") / 1e9,
                    "domestic_cap_bn": sum((r["market_cap"] or 0) for r in eq_prev if r["code"] not in CROSS_LISTED) / 1e9,
                    "deals": None}
        # counters missing from the previous day's feed: carry their (unchanged) capitalisation
        for e in equities:
            if e["code"] not in prev_map:
                prev_tot["market_cap_bn"] += e["market_cap_bn"]
                if not e["cross_listed"]:
                    prev_tot["domestic_cap_bn"] += e["market_cap_bn"]
        if prev_snapshot and prev_snapshot.get("date") == iso(prev_d):
            pt = prev_snapshot.get("totals", {})
            for k in ("turnover", "volume", "market_cap_bn", "domestic_cap_bn", "deals"):
                if pt.get(k) is not None:
                    prev_tot[k] = pt[k]
        elif prev_report and prev_report["equities"].get("total"):
            pr = prev_report["equities"]["total"]
            prev_tot.update({"turnover": pr["turnover"], "volume": pr["volume"], "deals": int(pr["deals"]),
                             "market_cap_bn": pr["market_cap_bn"]})
            prev_tot["domestic_cap_bn"] = pr["market_cap_bn"] - sum(r["market_cap_bn"] for r in prev_report["equities"]["rows"] if r["code"] in CROSS_LISTED)
        if report is None:
            try:
                ov = self.dse.overview(d)
                if ov.get("of_date") == iso(d) and ov.get("deals"):
                    tot["deals"] = int(ov["deals"])
                    self.notes.append("Deal count is the exchange-wide total (equities plus ETFs) until the DSE Market Report is published.")
            except Exception:  # noqa: BLE001
                pass
        if report and report["equities"].get("total"):
            rt = report["equities"]["total"]
            if rt.get("turnover") and abs(rt["turnover"] - tot["turnover"]) / rt["turnover"] > 0.005:
                self.notes.append("Equity turnover in the DSE feed and the DSE Market Report differ slightly; the report's figure is shown.")
                tot["turnover"], tot["volume"], tot["deals"] = rt["turnover"], rt["volume"], int(rt["deals"])

        # ── ETFs ───────────────────────────────────────────────────
        etf_rows = (report or {}).get("etfs", {}).get("rows", [])
        etf_cap_today = (report or {}).get("etfs", {}).get("total", {}) .get("market_cap_bn") if report else None
        if etf_cap_today is None:
            try:
                ov = self.dse.overview(d)
                if ov.get("of_date") == iso(d) and ov.get("market_cap_bn"):
                    etf_cap_today = round(ov["market_cap_bn"] - tot["market_cap_bn"], 2)
            except Exception:  # noqa: BLE001
                pass
        etf_cap_prev = None
        if prev_snapshot and prev_snapshot.get("date") == iso(prev_d):
            etf_cap_prev = prev_snapshot.get("market_caps", {}).get("etf", {}).get("today")
        if etf_cap_prev is None and prev_report and (prev_report.get("etfs") or {}).get("total"):
            etf_cap_prev = prev_report["etfs"]["total"].get("market_cap_bn")
        if etf_cap_prev is None and report and report.get("indicator_columns") and len(report["indicator_columns"]) > 1 \
                and report["indicator_columns"][1] == prev_d:
            v = report.get("indicators", {}).get("ETF Market Capitalisation (TZS bln)") or []
            etf_cap_prev = v[1] if len(v) > 1 else None
        if not etf_rows:
            # fallback: price/volume from the per-security summary, no turnover breakdown
            for code, r in summ.items():
                if code.endswith("-ETF"):
                    etf_rows.append({"code": code, "prev_close": None, "close": r["close"], "high": r["high"],
                                     "low": r["low"], "turnover": None, "deals": r["trades"], "volume": None,
                                     "market_cap_bn": None, "bids": None, "offers": None})
        for e in etf_rows:
            e["change_pct"] = pct_change(e.get("close"), e.get("prev_close"))

        # ── indices ───────────────────────────────────────────────
        indices = []
        for code in INDEX_ORDER:
            t, p = idx_today.get(code), idx_prev.get(code)
            if not t:
                continue
            prev_close = p["close"] if p else (t["close"] - t["change_pts"] if t.get("change_pts") is not None else None)
            indices.append({"code": code, "name": INDEX_NAMES[code], "close": t["close"], "prev_close": prev_close,
                            "change_pts": (t["close"] - prev_close) if prev_close else t.get("change_pts"),
                            "change_pct": pct_change(t["close"], prev_close)})

        # ── bonds traded, grouped by tenor ────────────────────────
        trades = (report or {}).get("bond_trades", {}).get("rows", [])
        by_term = {}
        for tr in trades:
            term = int(tr["term"]) if tr.get("term") else None
            g = by_term.setdefault(term, {"term": term, "deals": 0, "amount_bn": 0.0, "px": 0.0, "yl": 0.0, "n": 0})
            amt = tr.get("amount_bn") or 0.0
            g["deals"] += int(tr.get("deals") or 1)
            g["amount_bn"] += amt
            g["px"] += (tr.get("price") or 0.0) * amt
            g["yl"] += (tr.get("yield") or 0.0) * amt
            g["n"] += 1
        bonds_by_term = []
        for term in TENORS:
            g = by_term.get(term)
            if g and g["amount_bn"] > 0:
                bonds_by_term.append({"term": term, "deals": g["deals"], "turnover_mln": g["amount_bn"] * 1000.0,
                                      "wa_price": g["px"] / g["amount_bn"], "wa_yield": g["yl"] / g["amount_bn"]})
            else:
                bonds_by_term.append({"term": term, "deals": 0, "turnover_mln": 0.0, "wa_price": None, "wa_yield": None})
        other_terms = [g for t, g in by_term.items() if t not in TENORS and g["amount_bn"] > 0]
        for g in other_terms:
            bonds_by_term.append({"term": g["term"], "deals": g["deals"], "turnover_mln": g["amount_bn"] * 1000.0,
                                  "wa_price": g["px"] / g["amount_bn"], "wa_yield": g["yl"] / g["amount_bn"]})
        total_amt = sum(b["turnover_mln"] for b in bonds_by_term)
        bonds = {
            "trades": trades, "by_term": bonds_by_term,
            "total_turnover_mln": total_amt, "total_deals": sum(b["deals"] for b in bonds_by_term),
            "wa_price": (sum((b["wa_price"] or 0) * b["turnover_mln"] for b in bonds_by_term) / total_amt) if total_amt else None,
            "wa_yield": (sum((b["wa_yield"] or 0) * b["turnover_mln"] for b in bonds_by_term) / total_amt) if total_amt else None,
            "face_value_bn": (report or {}).get("gov_bonds_value_bn", {}).get("face") if report else None,
            "transaction_value_bn": (report or {}).get("gov_bonds_value_bn", {}).get("transaction") if report else None,
            "corporate_note": (report or {}).get("corporate_bonds_note") if report else None,
            "available": report is not None,
        }
        if report is None:
            bonds["total_deals"] = None  # the per-security summary endpoint is truncated; do not guess

        # ── market caps / indicators ──────────────────────────────
        market_caps = {
            "total": {"today": tot["market_cap_bn"], "prev": prev_tot["market_cap_bn"]},
            "domestic": {"today": tot["domestic_cap_bn"], "prev": prev_tot["domestic_cap_bn"]},
            "etf": {"today": etf_cap_today, "prev": etf_cap_prev},
        }
        outstanding = {}
        if report:
            for k, v in report.get("indicators", {}).items():
                if k.startswith("Outstanding") and v:
                    outstanding[k] = v[0]
        fx = {}
        if report:
            for k, v in report.get("indicators", {}).items():
                if k.startswith("TZS/") and v:
                    fx[k.split(" ")[0]] = {"today": v[0],
                                           "prev": v[1] if (len(v) > 1 and report.get("indicator_columns", [None, None])[1] == prev_d) else None}

        # ── movers / gainers / losers ─────────────────────────────
        traded = [e for e in equities if (e["turnover"] or 0) > 0]
        top = sorted(traded, key=lambda e: -e["turnover"])[:4]
        others = tot["turnover"] - sum(e["turnover"] for e in top)
        movers = [{"code": e["code"], "turnover": e["turnover"], "share_pct": e["turnover"] / tot["turnover"] * 100 if tot["turnover"] else 0}
                  for e in top]
        if others > 0 and len(traded) > len(top):
            movers.append({"code": "Others", "turnover": others, "share_pct": others / tot["turnover"] * 100 if tot["turnover"] else 0})
        moved = [e for e in equities if e["change_pct"] not in (None, 0)]
        gainers = sorted([e for e in moved if e["change_pct"] > 0], key=lambda e: -e["change_pct"])[:3]
        losers = sorted([e for e in moved if e["change_pct"] < 0], key=lambda e: e["change_pct"])[:3]
        advancers = sum(1 for e in moved if e["change_pct"] > 0)
        decliners = sum(1 for e in moved if e["change_pct"] < 0)
        unchanged = len(equities) - advancers - decliners

        # ── other sources ─────────────────────────────────────────
        auctions = bot_mod.auctions(self.http)
        for err in auctions.get("errors", []):
            self.notes.append(f"BOT: {err}")
        cache_path = self.data_dir / "cis_cache.json"
        cache = load_json(cache_path, {})
        cis = cis_mod.collect(self.http, year, cache)
        save_json(cache_path, cache)
        for err in cis.get("errors", []):
            self.notes.append(f"Fund NAVs: {err}")
        for e in etf_rows:  # attach a NAV only if it is fresh
            nv = cis["etf_navs"].get(e["code"])
            if nv and nv.get("date") and (d - nv["date"]).days <= 5:
                e["nav"] = nv["nav"]
                e["premium_pct"] = pct_change(e.get("close"), nv["nav"])
            else:
                e["nav"], e["premium_pct"] = None, None

        dataset = {
            "date": iso(d), "prev_date": iso(prev_d), "generated_at": now_eat().isoformat(timespec="minutes"),
            "sources": {"dse_report_url": report_url, "dse_report_found": report is not None,
                        "dse_api": "https://dse.co.tz/", "bot": "https://www.bot.go.tz/",
                        "cis": sorted({f["source"] for f in cis["funds"]})},
            "headline": (report or {}).get("headline"), "block_trades": (report or {}).get("block_trades"),
            "equities": equities, "totals": tot, "prev_totals": prev_tot,
            "breadth": {"advancers": advancers, "decliners": decliners, "unchanged": unchanged, "traded": len(traded)},
            "indices": indices, "market_caps": market_caps, "outstanding": outstanding, "fx": fx,
            "participation": (report or {}).get("participation", {}),
            "movers": movers, "gainers": gainers, "losers": losers,
            "bonds": bonds, "etfs": etf_rows,
            "cis": cis["funds"], "auctions": {"bond": auctions.get("bond"), "tbill": auctions.get("tbill")},
            "notes": self.notes,
        }
        dataset["history"] = self.update_history(dataset)
        return dataset

    # ── rolling history for the trend tiles ───────────────────────
    def update_history(self, ds: dict) -> list[dict]:
        path = self.data_dir / "history.json"
        hist = {h["date"]: h for h in load_json(path, [])}
        d = parse_iso(ds["date"])
        # backfill from the API if we have fewer than HISTORY_DAYS points before today
        earlier = sorted(k for k in hist if k < ds["date"])
        if len(earlier) < HISTORY_DAYS - 1:
            probe = d - timedelta(days=1)
            got = 0
            tries = 0
            while got < (HISTORY_DAYS - 1 - len(earlier)) and tries < 70:
                tries += 1
                if iso(probe) in hist:
                    probe -= timedelta(days=1)
                    continue
                if probe.weekday() >= 5:
                    probe -= timedelta(days=1)
                    continue
                try:
                    rows = self.dse.equities(probe)
                    td = parse_iso(rows[0]["trade_date"]) if rows else None
                    if td and td == probe:
                        idx = {r["code"]: r["close"] for r in self.dse.indices(probe)}
                        hist[iso(probe)] = {"date": iso(probe), "turnover": _sum(rows, "turnover"),
                                            "volume": _sum(rows, "volume"), "market_cap_bn": _sum(rows, "market_cap") / 1e9,
                                            "dsei": idx.get("DSEI"), "tsi": idx.get("TSI")}
                        got += 1
                    elif td and td < probe:
                        probe = td  # jump straight to the last trading day
                        continue
                except Exception as e:  # noqa: BLE001
                    self.log(f"history backfill {probe}: {e}")
                probe -= timedelta(days=1)
        idx = {i["code"]: i["close"] for i in ds["indices"]}
        hist[ds["date"]] = {"date": ds["date"], "turnover": ds["totals"]["turnover"], "volume": ds["totals"]["volume"],
                            "market_cap_bn": ds["totals"]["market_cap_bn"], "dsei": idx.get("DSEI"), "tsi": idx.get("TSI"),
                            "foreign_net_mln": (ds["participation"].get("equity") or {}).get("net_foreign_mln"),
                            "bond_turnover_mln": ds["bonds"]["total_turnover_mln"] if ds["bonds"]["available"] else None}
        out = [hist[k] for k in sorted(hist)]
        out = out[-400:]  # keep the file small
        save_json(path, out)
        return [h for h in out if h["date"] <= ds["date"]][-HISTORY_DAYS:]
