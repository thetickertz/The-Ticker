"""Collective investment schemes (unit trusts) and ETF net asset values.

Every manager publishes differently; each scraper is independent and best-effort, so a
redesign of one website only drops that manager's rows for the day (and the report says so).
"""
from __future__ import annotations

import re
from datetime import date

from .util import Http, html_tables, num, parse_date_loose, strip_tags

UTT_SCHEMES = {  # internal_name -> display
    "umoja": "Umoja Fund", "wekeza": "Wekeza Maisha Fund", "watoto": "Watoto Fund",
    "jikimu": "Jikimu Fund", "liquid": "Liquid Fund", "bond": "Bond Fund",
}


def _series_stats(points: list[tuple[date, float, float | None]], year_start_nav: float | None):
    """points sorted desc by date: (date, nav_per_unit, nav_total). Returns latest/prev/ytd."""
    if not points:
        return None
    d0, nav0, tot0 = points[0]
    prev = next((p for p in points[1:] if p[0] < d0), None)
    daily = ((nav0 / prev[1]) - 1) * 100 if prev and prev[1] else None
    ytd = ((nav0 / year_start_nav) - 1) * 100 if year_start_nav else None
    days = (d0 - date(d0.year - 1, 12, 31)).days
    # a linear extrapolation is meaningless in the first weeks of a year
    ann = (ytd * 365.0 / days) if (ytd is not None and days >= 30) else None
    return {"date": d0, "nav_per_unit": nav0, "nav_total": tot0, "prev_date": prev[0] if prev else None,
            "prev_nav_per_unit": prev[1] if prev else None, "daily_change_pct": daily,
            "year_start_nav": year_start_nav, "ytd_pct": ytd, "annualised_pct": ann}


def _year_start_from(points: list[tuple[date, float, float | None]], year: int):
    """Last valuation dated in the previous calendar year (the YTD base)."""
    prev_year = [p for p in points if p[0].year == year - 1]
    return max(prev_year, key=lambda p: p[0])[1] if prev_year else None


# ───────────────────────── UTT AMIS (6 funds) ─────────────────────────
def utt_amis(http: Http, year: int, cache: dict) -> list[dict]:
    s = http.s
    page = http.get("https://www.uttamis.co.tz/fund-performance").text
    tok = re.search(r'name="csrf-token" content="([^"]+)"', page)
    cols = ["DT_RowIndex", "sname", "net_asset_value", "outstanding_number_of_units", "nav_per_unit",
            "sale_price_per_unit", "repurchase_price_per_unit", "date_valued"]
    names = ["DT_RowIndex", "sname.name", "net_asset_value", "outstanding_number_of_units", "nav_per_unit",
             "sale_price_per_unit", "repurchase_price_per_unit", "date_valued"]

    def query(length=60, search=""):
        data = {"draw": "1", "start": "0", "length": str(length), "search[value]": search, "search[regex]": "false",
                "order[0][column]": "7", "order[0][dir]": "desc"}
        for i, (c, n) in enumerate(zip(cols, names)):
            data[f"columns[{i}][data]"] = c
            data[f"columns[{i}][name]"] = n
            data[f"columns[{i}][searchable]"] = "false" if i == 0 else "true"
            data[f"columns[{i}][orderable]"] = "false" if i == 0 else "true"
            data[f"columns[{i}][search][value]"] = ""
            data[f"columns[{i}][search][regex]"] = "false"
        r = http.post("https://www.uttamis.co.tz/navs", data=data,
                      headers={"X-CSRF-TOKEN": tok.group(1) if tok else "", "X-Requested-With": "XMLHttpRequest",
                               "Accept": "application/json"})
        r.raise_for_status()
        return r.json().get("data") or []

    rows = query(length=80)
    by_scheme: dict[str, list] = {}
    for r in rows:
        key = r.get("internal_name") or r.get("scheme_name")
        d = parse_date_loose(r.get("date_valued", ""))
        if not d:
            continue
        by_scheme.setdefault(key, []).append((d, num(r.get("nav_per_unit")), num(r.get("net_asset_value"))))

    # year-start NAV per scheme: cached, else searched once (DataTables global search hits date_valued)
    ys_cache = cache.setdefault("utt_amis", {}).setdefault(str(year), {})
    missing = [k for k in by_scheme if k not in ys_cache]
    if missing:
        for back in range(0, 8):
            d = date(year - 1, 12, 31)
            from datetime import timedelta
            d = d - timedelta(days=back)
            found = query(length=50, search=d.strftime("%Y-%m-%d"))  # the API filters on the ISO form
            for r in found:
                key = r.get("internal_name") or r.get("scheme_name")
                if key in missing and key not in ys_cache and parse_date_loose(r.get("date_valued", "")) == d:
                    ys_cache[key] = num(r.get("nav_per_unit"))
            if all(k in ys_cache for k in missing):
                break

    out = []
    for key, pts in by_scheme.items():
        pts.sort(key=lambda p: p[0], reverse=True)
        st = _series_stats(pts, ys_cache.get(key))
        if st:
            out.append({**st, "fund": UTT_SCHEMES.get(key, key.title()), "manager": "UTT AMIS",
                        "source": "https://www.uttamis.co.tz/fund-performance"})
    order = list(UTT_SCHEMES.values())
    out.sort(key=lambda x: order.index(x["fund"]) if x["fund"] in order else 99)
    return out


# ───────────────────────── Inuka (Orbit Securities) ─────────────────────────
def inuka(http: Http, year: int) -> list[dict]:
    page = http.get("https://orbit.co.tz/inuka-fund").text
    out = []
    # each fund block: heading then a history table (Date | NAV | units | NAV/unit | sale | repurchase)
    blocks = re.split(r"(?i)(INUKA MONEY MARKET FUND|INUKA DOZEN INDEX FUND)", page)
    seen = set()
    for i in range(1, len(blocks) - 1, 2):
        name = blocks[i].upper()
        seg = blocks[i + 1]
        tables = [t for t in html_tables(seg) if len(t) > 3 and t[0] and t[0][0].lower().startswith("date")]
        if not tables:
            continue
        pts = []
        for row in tables[0][1:]:
            if len(row) < 4:
                continue
            d = parse_date_loose(row[0])
            if d:
                pts.append((d, num(row[3]), num(row[1])))
        if not pts:
            continue
        pts.sort(key=lambda p: p[0], reverse=True)
        key = "Inuka Money Market Fund" if "MONEY" in name else "Inuka Dozen Index Fund"
        if key in seen:
            continue
        seen.add(key)
        st = _series_stats(pts, _year_start_from(pts, year))
        if st:
            out.append({**st, "fund": key, "manager": "Orbit Securities", "source": "https://orbit.co.tz/inuka-fund"})
    return out


# ───────────────────────── Faida Fund (Watumishi Housing Investments) ─────────────────────────
def faida(http: Http, year: int) -> list[dict]:
    page = http.get("https://www.whi.go.tz/NavData/NavSwahili.php").text
    pts = []
    for t in html_tables(page):
        for row in t[1:]:
            if len(row) >= 4:
                d = parse_date_loose(row[0])
                if d:
                    pts.append((d, num(row[3]), num(row[1])))
    if not pts:
        return []
    pts.sort(key=lambda p: p[0], reverse=True)
    st = _series_stats(pts, _year_start_from(pts, year))
    return [{**st, "fund": "Faida Fund", "manager": "Watumishi Housing Investments",
             "source": "https://www.whi.go.tz/NavData/NavSwahili.php"}] if st else []


# ───────────────────────── ETF NAVs ─────────────────────────
def vertex_etf_nav(http: Http) -> dict | None:
    page = http.get("https://vertex.co.tz/vertex-etf/").text
    best = None
    for t in html_tables(page):
        if not t or "NAV" not in t[0]:
            continue
        hdr = t[0]
        di, ni = hdr.index("Date"), hdr.index("NAV")
        for row in t[1:]:
            if len(row) <= max(di, ni):
                continue
            d, nav = parse_date_loose(row[di]), num(row[ni])
            if d and nav and (best is None or d > best[0]):
                best = (d, nav)
    return {"code": "VERTEX-ETF", "date": best[0], "nav": best[1], "source": "https://vertex.co.tz/vertex-etf/"} if best else None


def collect(http: Http, year: int, cache: dict) -> dict:
    """Run every scraper; never raise."""
    funds, errors = [], []
    for name, fn in (("UTT AMIS", lambda: utt_amis(http, year, cache)), ("Inuka", lambda: inuka(http, year)),
                     ("Faida", lambda: faida(http, year))):
        try:
            rows = fn()
            if rows:
                funds.extend(rows)
            else:  # the page answered but carried no NAV rows (e.g. Orbit's "fund feed unavailable" notice)
                errors.append(f"{name} published no unit prices today; its rows are left out.")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: {e}")
    etf_navs = {}
    try:
        v = vertex_etf_nav(http)
        if v:
            etf_navs[v["code"]] = v
    except Exception as e:  # noqa: BLE001
        errors.append(f"Vertex ETF NAV: {e}")
    return {"funds": funds, "etf_navs": etf_navs, "errors": errors}
