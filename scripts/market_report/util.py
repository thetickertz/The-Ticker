"""Shared helpers: number parsing, formatting, dates and a retrying HTTP session."""
from __future__ import annotations

import re
import time
from datetime import date, datetime, timedelta, timezone

import requests

EAT = timezone(timedelta(hours=3), "EAT")
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36 TheTickerReportBot/1.0 (+https://thetickertz.github.io/The-Ticker/)")

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTHS_FULL = ["January", "February", "March", "April", "May", "June", "July", "August",
               "September", "October", "November", "December"]
_MONTH_LOOKUP = {m.lower(): i + 1 for i, m in enumerate(MONTHS_FULL)}
_MONTH_LOOKUP.update({m.lower(): i + 1 for i, m in enumerate(MONTHS)})
_MONTH_LOOKUP["sept"] = 9


# ───────────────────────────── numbers ─────────────────────────────
def num(s, default=None):
    """Parse '1,234.5', '-0.66', '(12.3)', '12.3%', '—' into a float (or default)."""
    if s is None:
        return default
    if isinstance(s, (int, float)):
        return float(s)
    t = str(s).strip().replace("\xa0", " ").replace(" ", "")
    if t in ("", "-", "—", "–", "n/a", "N/A", "null", "None"):
        return default
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()").replace(",", "").replace("%", "").replace("+", "")
    try:
        v = float(t)
    except ValueError:
        return default
    return -v if neg else v


def fnum(v, dp=0, dash="—"):
    """Thousands-separated number with dp decimals."""
    if v is None:
        return dash
    return f"{v:,.{dp}f}"


def fpct(v, dp=1, sign=True, dash="—"):
    if v is None:
        return dash
    s = f"{v:+,.{dp}f}%" if sign else f"{v:,.{dp}f}%"
    return s.replace("+0.0%", "0.0%").replace("-0.0%", "0.0%") if dp == 1 else s


def tzs_compact(v, dp=2, dash="—"):
    """TZS 3.30 billion / TZS 786.2 million / TZS 98,470."""
    if v is None:
        return dash
    a = abs(v)
    if a >= 1e12:
        return f"TZS {v/1e12:,.{dp}f} trillion"
    if a >= 1e9:
        return f"TZS {v/1e9:,.{dp}f} billion"
    if a >= 1e6:
        return f"TZS {v/1e6:,.1f} million"
    return f"TZS {v:,.0f}"


def shares_compact(v, dash="—"):
    if v is None:
        return dash
    if v >= 1e6:
        return f"{v/1e6:,.2f} million shares"
    return f"{v:,.0f} shares"


def pct_change(new, old):
    if new is None or old in (None, 0):
        return None
    return (new / old - 1.0) * 100.0


def ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


# ───────────────────────────── dates ─────────────────────────────
def iso(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def parse_iso(s: str) -> date:
    return datetime.strptime(s[:10], "%Y-%m-%d").date()


def parse_date_loose(s: str):
    """'1st October 2026', '01-10-2026', '30 Sept 26', '2026-10-01', '10 November 2025', '30-09-26'."""
    if not s:
        return None
    t = re.sub(r"(\d)\s*(st|nd|rd|th)\b", r"\1", s.strip(), flags=re.I)
    t = t.replace(",", " ")
    t = re.sub(r"(?<=\d)-(?=[A-Za-z])|(?<=[A-Za-z])-(?=\d)", " ", t)  # 23-SEP-2026
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", t)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search(r"(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})", t)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000
        try:
            return date(y, mo, d)
        except ValueError:
            return None
    m = re.search(r"(\d{1,2})\s+([A-Za-z]+)\.?\s+(\d{2,4})", t)
    if m:
        mo = _MONTH_LOOKUP.get(m.group(2).lower())
        if mo:
            y = int(m.group(3))
            if y < 100:
                y += 2000
            try:
                return date(y, mo, int(m.group(1)))
            except ValueError:
                return None
    m = re.search(r"([A-Za-z]+)\s+(\d{1,2})\s+(\d{4})", t)  # 'September 30 2026'
    if m:
        mo = _MONTH_LOOKUP.get(m.group(1).lower())
        if mo:
            try:
                return date(int(m.group(3)), mo, int(m.group(2)))
            except ValueError:
                return None
    return None


def human_date(d: date) -> str:
    return f"{d.strftime('%A')}, {d.day} {MONTHS_FULL[d.month-1]} {d.year}"


def short_date(d: date) -> str:
    return f"{d.day} {MONTHS[d.month-1]} {d.year}"


def tiny_date(d: date) -> str:
    return f"{d.day} {MONTHS[d.month-1]} {str(d.year)[2:]}"


def now_eat() -> datetime:
    return datetime.now(EAT)


# ───────────────────────────── HTTP ─────────────────────────────
class Http:
    """Small retrying wrapper so one flaky source never kills the build."""

    def __init__(self, timeout=60, retries=3, backoff=2.0):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept-Language": "en"})
        self.timeout, self.retries, self.backoff = timeout, retries, backoff

    def _do(self, method, url, **kw):
        last = None
        for i in range(self.retries):
            try:
                r = self.s.request(method, url, timeout=self.timeout, **kw)
                if r.status_code >= 500:
                    raise requests.HTTPError(f"{r.status_code} from {url}")
                return r
            except Exception as e:  # noqa: BLE001 - any transport error is retried
                last = e
                time.sleep(self.backoff * (i + 1))
        raise RuntimeError(f"{method} {url} failed after {self.retries} attempts: {last}")

    def get(self, url, **kw):
        return self._do("GET", url, **kw)

    def post(self, url, **kw):
        return self._do("POST", url, **kw)

    def json(self, url, **kw):
        r = self.get(url, headers={"Accept": "application/json"}, **kw)
        r.raise_for_status()
        return r.json()


def strip_tags(html: str) -> str:
    import html as _h
    t = re.sub(r"<script.*?</script>", "", html, flags=re.S)
    t = re.sub(r"<style.*?</style>", "", t, flags=re.S)
    t = re.sub(r"<svg.*?</svg>", "", t, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", _h.unescape(t)).strip()


def html_tables(html: str):
    """Return every <table> as a list of rows (each a list of cell strings)."""
    import html as _h
    out = []
    for tb in re.findall(r"<table.*?</table>", html, flags=re.S):
        rows = []
        for tr in re.findall(r"<tr.*?</tr>", tb, flags=re.S):
            cells = [re.sub(r"\s+", " ", _h.unescape(re.sub(r"<[^>]+>", " ", c))).strip()
                     for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.S)]
            if cells:
                rows.append(cells)
        out.append(rows)
    return out
