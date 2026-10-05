"""Dar es Salaam Stock Exchange sources.

Two tiers, so the build never depends on one thing:
  1. Public JSON endpoints used by dse.co.tz's own homepage (equities, indices, overview,
     per-security daily summary, movers).
  2. The exchange's own "Market Report" for the day, published on the homepage as a
     pdf2htmlEX page. It carries what the JSON does not: foreign/local participation,
     every bond trade with price/yield, ETF prices, outstanding bids/offers.
"""
from __future__ import annotations

import html as _h
import re
from datetime import date

from .util import Http, iso, num, parse_date_loose

BASE = "https://dse.co.tz"
CROSS_LISTED = {"EABL", "JHL", "KA", "KCB", "NMG", "USL"}  # listed primarily in Nairobi/Kampala

INDEX_NAMES = {
    "DSEI": "All Share Index (DSEI)",
    "TSI": "Tanzania Share Index (TSI)",
    "IA": "Industrial & Allied (IA)",
    "BI": "Banks, Finance & Investment (BI)",
    "CS": "Commercial Services (CS)",
}
INDEX_ORDER = ["DSEI", "TSI", "IA", "BI", "CS"]


class DSE:
    def __init__(self, http: Http | None = None):
        self.http = http or Http()

    # ── JSON endpoints ──────────────────────────────────────────────
    def last_trade_date(self) -> date:
        j = self.http.json(f"{BASE}/get/last/trade/date")
        return parse_date_loose(str(j["data"])[:10])

    def equities(self, d: date) -> list[dict]:
        """End-of-day row per counter for the last trading day on or before d."""
        j = self.http.json(f"{BASE}/api/get/market/prices/for/range",
                           params={"to_date": iso(d), "isLastTradeTrend": 1,
                                   "security_code": "ALL", "class": "EQUITY"})
        rows = []
        for r in j.get("data") or []:
            rows.append({
                "code": r["company"],
                "trade_date": str(r.get("trade_date", ""))[:10],
                "open": num(r.get("opening_price")),
                "close": num(r.get("closing_price")),
                "high": num(r.get("high")),
                "low": num(r.get("low")),
                "prev_close": num(r.get("prev_close")),
                "change_pct": num(r.get("change")),
                "turnover": num(r.get("turnover")) or 0.0,
                "volume": num(r.get("volume")) or 0.0,
                "shares_in_issue": num(r.get("shares_in_issue")),
                "market_cap": num(r.get("market_cap")),
            })
        return rows

    def indices(self, d: date) -> list[dict]:
        j = self.http.json(f"{BASE}/get/last/traded/indices", params={"from": iso(d)})
        out = []
        for r in j.get("data") or []:
            out.append({"code": r.get("Code"), "name": INDEX_NAMES.get(r.get("Code"), r.get("IndexDescription")),
                        "close": num(r.get("ClosingPrice")), "change_pts": num(r.get("Change"))})
        out.sort(key=lambda x: INDEX_ORDER.index(x["code"]) if x["code"] in INDEX_ORDER else 99)
        return out

    def overview(self, d: date) -> dict:
        """Market-wide aggregate incl. ETFs: volume, deals, turnover, market cap (TZS bn)."""
        j = self.http.json(f"{BASE}/get/market/over/view", params={"to_date": iso(d)})
        return {"volume": num(j.get("volume")), "deals": num(j.get("deals")),
                "turnover": num(j.get("turn_over")), "market_cap_bn": num(j.get("m_cap_aggregate")),
                "of_date": str(j.get("of_date", ""))[:10]}

    def daily_summary(self, d: date) -> list[dict]:
        """Per-security trade count, high/low/close — covers equities, ETFs and bonds."""
        j = self.http.json(f"{BASE}/api/get/trade/daily/summary", params={"from": iso(d)})
        return [{"code": r.get("company"), "trades": num(r.get("number_of_trades")) or 0,
                 "high": num(r.get("price_high")), "low": num(r.get("price_low")),
                 "close": num(r.get("closing_price")), "trade_date": str(r.get("trade_date", ""))[:10]}
                for r in j.get("data") or []]

    def closing_price_on_or_before(self, code: str, d: date):
        j = self.http.json(f"{BASE}/api/get/market/prices/for/range",
                           params={"to_date": iso(d), "isLastTradeTrend": 1,
                                   "security_code": code, "class": "EQUITY"})
        rows = j.get("data") or []
        if not rows:
            return None
        return num(rows[0].get("closing_price")), str(rows[0].get("trade_date", ""))[:10], num(rows[0].get("shares_in_issue"))

    def price_series(self, code: str, days: int = 400) -> list[dict]:
        """Daily closes (ascending) for one counter — used to detect share splits."""
        j = self.http.json(f"{BASE}/api/get/market/prices/for/range/duration",
                           params={"security_code": code, "days": days, "class": "EQUITY"})
        rows = [{"date": str(r.get("trade_date", ""))[:10], "close": num(r.get("closing_price")),
                 "shares": num(r.get("shares_in_issue"))} for r in j.get("data") or []]
        rows.sort(key=lambda r: r["date"])
        return rows

    # ── the exchange's own daily Market Report ─────────────────────
    def daily_report_links(self) -> list[tuple[date | None, str]]:
        """[(report_date, url)] from the homepage 'Daily Market Reports' cards, newest first."""
        page = self.http.get(f"{BASE}/").text
        i = page.find('id="daily-reports"')
        seg = page[i:] if i >= 0 else page
        seg = re.sub(r"<svg.*?</svg>", "", seg, flags=re.S)  # the card icons are huge inline SVGs
        out = []
        for m in re.finditer(r'href="(https://dse\.co\.tz/get/daily/report/[^"]+)"', seg):
            before = seg[max(0, m.start() - 2500):m.start()]
            # the card reads: <span>Date: </span> 1<sup>st</sup> October 2026
            dm = list(re.finditer(r"Date:\s*</span>\s*(.*?)</p>", before, flags=re.S))
            d = None
            if dm:
                d = parse_date_loose(re.sub(r"<[^>]+>", "", dm[-1].group(1)))
            out.append((d, _h.unescape(m.group(1))))
        return out

    def fetch_report_lines(self, url: str) -> list[list[str]]:
        """pdf2htmlEX page → list of pages, each a list of text lines."""
        s = self.http.get(url).text
        if "pdf2htmlEX" not in s and 'class="pf' not in s:
            raise RuntimeError("daily report link did not return a pdf2htmlEX page")
        pages = re.split(r'<div id="pf[0-9a-f]+"', s)[1:]
        out = []
        for pg in pages:
            lines = []
            for ln in re.findall(r'<div class="t [^"]*"[^>]*>(.*?)</div>', pg, flags=re.S):
                txt = _h.unescape(re.sub(r"<[^>]+>", "", ln)).replace("\xa0", " ")
                txt = re.sub(r"\s+", " ", txt).strip()
                if txt:
                    lines.append(txt)
            out.append(lines)
        return out


# ───────────────────────── report parsing ─────────────────────────
_NUM = re.compile(r"^-?\(?[\d,]*\.?\d+\)?%?$")


def _is_num(tok: str) -> bool:
    return bool(_NUM.match(tok))


def _labelled_block(lines: list[str], labels: list[str]) -> dict[str, list[float]]:
    """For tables rendered as 'label' then one number per line: {label: [numbers...]}."""
    out, cur = {}, None
    norm = {re.sub(r"\s+", " ", l).lower(): l for l in labels}
    for ln in lines:
        key = re.sub(r"\s+", " ", ln).lower().rstrip(":")
        if key in norm:
            cur = norm[key]
            out[cur] = []
            continue
        if cur is not None and _is_num(ln):
            out[cur].append(num(ln))
        elif cur is not None and ln.strip() and not _is_num(ln):
            # a continuation label like 'Foreign Investors:' – keep collecting
            if ln.strip().lower().startswith("foreign investors"):
                continue
            cur = None
    return out


def parse_report(pages: list[list[str]]) -> dict:
    """Pull every table we need out of the exchange's Market Report."""
    flat = [ln for pg in pages for ln in pg]
    text = "\n".join(flat)
    rep: dict = {"raw_pages": len(pages)}

    # date on page 1: 'Thursday, 01' / 'st' / 'October 2026' (split across lines)
    head = " ".join(pages[0][:6]) if pages else ""
    rep["report_date"] = parse_date_loose(re.sub(r",", " ", head.replace("Market Report", "")))

    # headline narrative sentence
    m = re.search(r"DSE recorded a total turnover of (.*?)(?:\n|$)(?:(.*?deals\.))?", text, flags=re.S)
    rep["headline"] = " ".join(x for x in (m.group(1), m.group(2)) if x).replace("\n", " ") if m else None
    bt = re.search(r"On the Block Trade Pre-arranged Market board,(.*?)\.\n", text, flags=re.S)
    rep["block_trades"] = ("On the block-trade board," + bt.group(1)).replace("\n", " ") if bt else None

    # participation (equities / ETF)
    part_labels = ["Total Turnover", "Turnover from Shares Bought by", "%Buying Local Investors",
                   "%Buying Foreign Investors", "Turnover from Shares Sold by", "%Selling Local Investors",
                   "%Selling Foreign Investors"]
    rep["participation"] = {}
    section_titles = ("Equities Market Turnover", "ETF Market Turnover", "Value of Government Bonds",
                      "Value of Corporate Bonds", "Key Market Indicators")
    for key, title in (("equity", "Equities Market Turnover (in million TZS)"),
                       ("etf", "ETF Market Turnover (in million TZS)")):
        if title in flat:
            i = flat.index(title)
            end = next((k for k in range(i + 1, min(len(flat), i + 80))
                        if flat[k].startswith(section_titles)), min(len(flat), i + 80))
            blk = _labelled_block(flat[i + 1:end], part_labels)
            first = {k: (v[0] if v else None) for k, v in blk.items()}
            if first.get("Total Turnover") is not None:
                fb, fs = first.get("Turnover from Shares Bought by"), first.get("Turnover from Shares Sold by")
                rep["participation"][key] = {
                    "total_turnover_mln": first.get("Total Turnover"),
                    "foreign_buy_mln": fb, "foreign_sell_mln": fs,
                    "pct_buy_local": first.get("%Buying Local Investors"),
                    "pct_buy_foreign": first.get("%Buying Foreign Investors"),
                    "pct_sell_local": first.get("%Selling Local Investors"),
                    "pct_sell_foreign": first.get("%Selling Foreign Investors"),
                    "net_foreign_mln": (fb - fs) if (fb is not None and fs is not None) else None,
                }

    # value of government bonds traded (bn): first two numbers = face value, transaction value for the day
    i = next((k for k, ln in enumerate(flat) if ln.startswith("Value of Government Bonds Traded")), None)
    if i is not None:
        nums = [num(x) for x in flat[i:i + 30] if _is_num(x)]
        if len(nums) >= 2:
            rep["gov_bonds_value_bn"] = {"face": nums[0], "transaction": nums[1]}
    rep["corporate_bonds_note"] = "There was no activity in the Corporate Bonds segment." \
        if "no activity in the Corporate Bonds" in text else None

    # key market indicators / FX (first number after each label = report day)
    ind_labels = ["Total Market Capitalisation (TZS bln)", "Domestic Market Capitalisation (TZS bln)",
                  "ETF Market Capitalisation (TZS bln)", "Outstanding Government Bonds (TZS bln)",
                  "Outstanding Corporate Bonds (TZS bln)", "Outstanding Sustainable Bonds (TZS bln)",
                  "Outstanding Sustainable Bonds (USD mln)", "Outstanding Sub-national Bonds (TZS bln)",
                  "Outstanding Sukuk Bonds (TZS bln)", "Outstanding Sukuk Bonds (USD mln)",
                  "Outstanding Infrastructure Bonds (TZS bln)", "All Share Index (DSEI)",
                  "Tanzania Share Index (TSI)", "Industrial & Allied (IA)", "Banks, Finance & Investment (BI)",
                  "Commercial Services (CS)", "TZS/USD (BOT Mean Rate)", "TZS/KE (BOT Mean Rate)",
                  "TZS/GBP (BOT Mean Rate)"]
    i = next((k for k, ln in enumerate(flat) if ln.startswith("Key Market Indicators")), None)
    if i is not None:
        blk = _labelled_block(flat[i:i + 140], ind_labels)
        rep["indicators"] = {k: v for k, v in blk.items()}
        # the three column headers right after the title, e.g. '01 Oct 26' / '30 Sept 26' / '31 Oct 25'
        rep["indicator_columns"] = [parse_date_loose(x) for x in flat[i + 1:i + 4]]

    # equity table: tokens after the header; a row starts at a counter code
    rep["equities"] = _parse_equity_table(pages)
    rep["etfs"] = _parse_etf_table(pages)
    rep["bond_trades"] = _parse_bond_table(pages)
    return rep


_EQ_HEADER_END = "Offers"


def _page_kind(pg: list[str]) -> str | None:
    """Classify a report page by its table header: 'equity', 'etf', 'bond' or None."""
    head = " ".join(pg[:40])
    if "ETF DAILY PRICES" in head:
        return "etf"
    if "Daily Price Information" in head or ("Clean Price" in head and "Bond No." in head):
        return "bond"
    if "EQUITY DAILY PRICES" in head or ("Outstanding" in head and "Co." in head and "Market Cap" in head):
        return "equity"
    return None


def _page_tokens_after(pages, kind: str, header_last: str):
    """Tokens of every page of the given kind, after the last header token."""
    toks = []
    for pg in pages:
        if _page_kind(pg) != kind:
            continue
        words = []
        for ln in pg:
            words.extend(ln.split())
        # skip the page header: find last occurrence of header_last within the first ~120 tokens
        idx = None
        for k, w in enumerate(words[:160]):
            if w == header_last:
                idx = k
        if idx is None:
            continue
        toks.extend(words[idx + 1:])
    return toks


def _parse_equity_table(pages):
    toks = _page_tokens_after(pages, "equity", _EQ_HEADER_END)
    rows, k, total = [], 0, None
    while k < len(toks):
        t = toks[k]
        if t == "Total":
            vals = [num(x) for x in toks[k + 1:k + 5] if _is_num(x)]
            if len(vals) >= 4:
                total = {"turnover": vals[0], "deals": vals[1], "volume": vals[2], "market_cap_bn": vals[3]}
            k += 5
            continue
        if re.fullmatch(r"[A-Z][A-Z0-9\-]{1,11}", t) and not _is_num(t):
            vals = []
            j = k + 1
            while j < len(toks) and len(vals) < 11 and _is_num(toks[j]):
                vals.append(num(toks[j]))
                j += 1
            if len(vals) == 11:
                o, c, hi, lo, to, de, vo, mc, bids, offers = vals[0], vals[1], vals[2], vals[3], vals[4], vals[5], vals[6], vals[7], vals[8], vals[9]
                rows.append({"code": t, "prev_close": o, "close": c, "high": hi, "low": lo, "turnover": to,
                             "deals": de, "volume": vo, "market_cap_bn": mc, "bids": bids, "offers": offers})
                k = j
                continue
            if len(vals) == 10:  # same layout, if a column is ever dropped
                rows.append({"code": t, "prev_close": vals[0], "close": vals[1], "high": vals[2], "low": vals[3],
                             "turnover": vals[4], "deals": vals[5], "volume": vals[6], "market_cap_bn": vals[7],
                             "bids": vals[8], "offers": vals[9]})
                k = j
                continue
        k += 1
    return {"rows": rows, "total": total}


def _parse_etf_table(pages):
    toks = _page_tokens_after(pages, "etf", _EQ_HEADER_END)
    rows, k, total = [], 0, None
    while k < len(toks):
        t = toks[k]
        if t == "Total":
            vals = [num(x) for x in toks[k + 1:k + 5] if _is_num(x)]
            if len(vals) >= 4:
                total = {"turnover": vals[0], "deals": vals[1], "volume": vals[2], "market_cap_bn": vals[3]}
            k += 5
            continue
        if t.endswith("-ETF"):
            vals = []
            j = k + 1
            while j < len(toks) and len(vals) < 10 and _is_num(toks[j]):
                vals.append(num(toks[j]))
                j += 1
            if len(vals) == 10:
                rows.append({"code": t, "prev_close": vals[0], "close": vals[1], "high": vals[2], "low": vals[3],
                             "turnover": vals[4], "deals": vals[5], "volume": vals[6], "market_cap_bn": vals[7],
                             "bids": vals[8], "offers": vals[9]})
                k = j
                continue
        k += 1
    return {"rows": rows, "total": total}


def _parse_bond_table(pages):
    """Rows like: 533 20 15.49 23/04/2020 23/04/2040 101/10/2026 15.15000 141.2080 10.6677 134.0359
    (deals and trade date are glued together: '1' + '01/10/2026')."""
    toks = _page_tokens_after(pages, "bond", "Price")
    # header ends with 'Clean Price' – _page_tokens_after cut at the LAST 'Price' in the first 160 tokens
    rows, total_amount, total_deals = [], None, None
    k = 0
    while k < len(toks):
        t = toks[k]
        if t == "Total":
            k += 1
            continue
        seq = toks[k:k + 10]
        if (len(seq) == 10 and re.fullmatch(r"\d{1,2}/\d{2}/\d{4}", seq[3]) and re.fullmatch(r"\d{1,2}/\d{2}/\d{4}", seq[4])
                and re.fullmatch(r"\d+/\d{2}/\d{4}", seq[5])):
            dealsdate = seq[5]
            deals = int(dealsdate[:-10]) if len(dealsdate) > 10 else None
            tdate = dealsdate[-10:]
            rows.append({"bond_no": seq[0], "term": num(seq[1]), "coupon": num(seq[2]), "issue_date": seq[3],
                         "maturity_date": seq[4], "deals": deals, "trade_date": tdate, "amount_bn": num(seq[6]),
                         "price": num(seq[7]), "yield": num(seq[8]), "clean_price": num(seq[9])})
            k += 10
            continue
        # trailing totals: '15.85600' then '8' (deals)
        if _is_num(t) and k + 1 < len(toks) and _is_num(toks[k + 1]) and (k + 2 >= len(toks) or toks[k + 2] == "Total"):
            total_amount, total_deals = num(t), int(num(toks[k + 1]) or 0)
            k += 2
            continue
        k += 1
    return {"rows": rows, "total_amount_bn": total_amount, "total_deals": total_deals}
