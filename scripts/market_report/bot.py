"""Bank of Tanzania primary-market auction results (the same endpoints the BOT site's
'View' buttons call)."""
from __future__ import annotations

import re

from .util import Http, html_tables, num, parse_date_loose

BASE = "https://www.bot.go.tz"


class BOT:
    def __init__(self, http: Http | None = None):
        self.http = http or Http()

    def _listing_rows(self, path: str):
        page = self.http.get(f"{BASE}{path}", params={"lang": "en"}).text
        rows = []
        for tr in re.findall(r"<tr.*?</tr>", page, flags=re.S):
            btn = re.search(r'id="showSummaryDetails"\s+value="([^"]+)"', tr)
            if not btn:
                continue
            cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c)).strip()
                     for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.S)]
            rows.append({"cells": cells, "value": btn.group(1)})
        return rows

    def latest_bond_auction(self) -> dict | None:
        rows = self._listing_rows("/TBonds")
        if not rows:
            return None
        r0 = rows[0]
        au_no, _, au_days = r0["value"].partition("_")
        resp = self.http.post(f"{BASE}/TBonds/AuctionSummaries", data={"au_no": au_no, "au_days": au_days or "1"},
                              headers={"X-Requested-With": "XMLHttpRequest"}).json()
        if str(resp.get("message", "")).upper().startswith("FAIL"):
            return None
        items = {str(it.get("itemDesc", "")).upper(): it for it in resp.get("tbondSummary") or []}

        def val(key_part, non=False):
            for k, it in items.items():
                if key_part in k:
                    return num(it.get("itemValueNon" if non else "itemValue"))
            return None

        title = resp.get("bondTitle", "")
        term = num((re.search(r"(\d+)-YEAR", title) or [None, None])[1])
        coupon = num((re.search(r"([\d.]+)%", title) or [None, None])[1])
        offered, tendered, successful = val("AMOUNT OFFERED"), val("TOTAL TENDERED"), val("SUCCESSFUL BIDS TZS")
        out = {
            "auction_no": au_no, "sale_no": au_days, "title": title, "isin": resp.get("ISIN"),
            "date": parse_date_loose(resp.get("BondDate", "")), "term": term, "coupon": coupon,
            "redemption_date": (items.get("REDEMPTION DATE") or {}).get("itemValue"),
            "bids_received": val("NUMBER OF BIDS RECEIVED"), "bids_successful": val("NUMBER OF SUCCESSFUL BIDS"),
            "highest_bid": val("HIGHEST BID"), "lowest_bid": val("LOWEST BID"),
            "min_successful_price": val("MINIMUM SUCCESSFUL PRICE"),
            "wap": val("WEIGHTED AVERAGE PRICE"), "way": val("YIELD-TO-MATURITY"),
            "wa_coupon_yield": val("COUPON YIELD"),
            "offered_mln": offered, "tendered_mln": tendered, "successful_mln": successful,
            "noncomp_offered_mln": val("AMOUNT OFFERED", True), "noncomp_tendered_mln": val("TOTAL TENDERED", True),
            "noncomp_successful_mln": val("SUCCESSFUL BIDS TZS", True),
            "bid_to_cover": (tendered / offered) if (tendered and offered) else None,
            "source": f"{BASE}/TBonds",
        }
        return out

    def latest_tbill_auction(self) -> dict | None:
        rows = self._listing_rows("/TBills")
        if not rows:
            return None
        au_no = rows[0]["value"]
        listed_date = next((parse_date_loose(c) for c in rows[0]["cells"] if parse_date_loose(c)), None)
        resp = self.http.post(f"{BASE}/Tbills/getTbillsDetails", data={"au_no": au_no},
                              headers={"X-Requested-With": "XMLHttpRequest"}).json()
        if str(resp.get("message", "")).startswith("ERROR"):
            return None
        matrix = resp.get("TbillData") or []
        if not matrix:
            return None
        tenors = [str(x).strip() for x in matrix[0][1:]]
        table = {}
        for row in matrix[1:]:
            label = str(row[0]).strip()
            table[label] = [num(x) if not re.search(r"[A-Za-z/]", str(x)) or re.fullmatch(r"[\d/]+", str(x)) else str(x)
                            for x in row[1:]]
            if "Maturity" in label:
                table[label] = [str(x) for x in row[1:]]

        def pick(part):
            for k, v in table.items():
                if part.lower() in k.lower():
                    return v
            return [None] * len(tenors)

        offered, tendered, succ = pick("Amount Offered"), pick("Amount Tendered"), pick("Successful Bids TZS")
        way = pick("Weighted Average Yield")
        return {
            "auction_no": au_no, "date": listed_date, "tenors": tenors,
            "maturity": pick("Maturity"), "bids": pick("Number of Bids"), "successful_bids": pick("Successful Bids")
            if "Successful Bids" in table else pick("Successful"),
            "highest": pick("Highest"), "lowest": pick("Lowest"), "min_successful": pick("Min. Successful"),
            "wap": pick("Weighted Average Price"), "way": way,
            "offered_mln": offered, "tendered_mln": tendered, "successful_mln": succ,
            "bid_to_cover": [(t / o) if (t and o) else None for t, o in zip(tendered, offered)],
            "source": f"{BASE}/TBills",
        }


def auctions(http: Http | None = None) -> dict:
    b = BOT(http)
    out = {"bond": None, "tbill": None, "errors": []}
    try:
        out["bond"] = b.latest_bond_auction()
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"bond auction: {e}")
    try:
        out["tbill"] = b.latest_tbill_auction()
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"t-bill auction: {e}")
    return out
