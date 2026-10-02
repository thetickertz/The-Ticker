"""Plain-language explanations generated from the numbers (rule-based, no model in the loop).

Tone: short sentences, every jargon term explained the first time it appears, numbers rounded
to what a reader can hold in their head. Each function returns HTML-safe strings; the
renderer escapes nothing here, so keep '&', '<' out of the text."""
from __future__ import annotations

from .util import fnum, fpct, parse_iso, short_date, shares_compact, tzs_compact

TENOR_WORDS = {2: "2-year", 5: "5-year", 7: "7-year", 10: "10-year", 15: "15-year", 20: "20-year", 25: "25-year"}


def _dir_word(pct, up="rose", down="fell", flat="was unchanged"):
    if pct is None:
        return flat
    if pct > 0.005:
        return up
    if pct < -0.005:
        return down
    return flat


def _ratio_words(new, old):
    """'about a third of', 'almost three times', 'a little above'..."""
    if not new or not old:
        return None
    r = new / old
    if r >= 2.8:
        return f"almost {r:.0f} times"
    if r >= 1.8:
        return f"about {r:.1f} times"
    if r >= 1.15:
        return f"{(r-1)*100:.0f}% more than"
    if r >= 0.9:
        return "about the same as"
    if r >= 0.6:
        return f"{(1-r)*100:.0f}% less than"
    if r >= 0.4:
        return "about half of"
    if r >= 0.27:
        return "about a third of"
    if r >= 0.18:
        return "about a quarter of"
    return f"only {r*100:.0f}% of"


def summary_bullets(ds: dict) -> list[str]:
    """The 'today in one minute' list."""
    t, p = ds["totals"], ds["prev_totals"]
    out = []
    ratio = _ratio_words(t["turnover"], p.get("turnover"))
    out.append(f"<b>{tzs_compact(t['turnover'])}</b> worth of shares changed hands in {fnum(t['deals'])} deals — "
               f"{ratio} the {tzs_compact(p['turnover'])} traded the previous session." if ratio
               else f"<b>{tzs_compact(t['turnover'])}</b> worth of shares changed hands in {fnum(t['deals'])} deals.")
    dsei = next((i for i in ds["indices"] if i["code"] == "DSEI"), None)
    tsi = next((i for i in ds["indices"] if i["code"] == "TSI"), None)
    if dsei and dsei.get("change_pct") is not None:
        w = _dir_word(dsei["change_pct"])
        tsi_txt = ""
        if tsi and tsi.get("change_pct") is not None:
            tsi_txt = f"; the local-companies index (TSI) {_dir_word(tsi['change_pct'])} {fpct(abs(tsi['change_pct']), sign=False)}"
        out.append(f"Prices overall <b>{w}</b>: the All Share Index (DSEI) {w} {fpct(abs(dsei['change_pct']), sign=False)} "
                   f"to {fnum(dsei['close'], 2)}{tsi_txt}.")
    b = ds["breadth"]
    if b["advancers"] or b["decliners"]:
        out.append(f"<b>{b['advancers']} counters closed higher, {b['decliners']} lower</b> and {b['unchanged']} were unchanged "
                   f"(a counter is one listed company's shares).")
    if ds["gainers"]:
        g = ds["gainers"][0]
        out.append(f"Best performer: <b>{g['code']}</b> {fpct(g['change_pct'])} to TZS {fnum(g['close'])}."
                   + (f" Weakest: <b>{ds['losers'][0]['code']}</b> {fpct(ds['losers'][0]['change_pct'])} to TZS {fnum(ds['losers'][0]['close'])}." if ds["losers"] else ""))
    pe = (ds.get("participation") or {}).get("equity")
    if pe and pe.get("net_foreign_mln") is not None:
        n = pe["net_foreign_mln"]
        if abs(n) < 50:
            out.append(f"Foreign investors were roughly <b>neutral</b>: they bought TZS {fnum(pe['foreign_buy_mln'],1)}m and sold TZS {fnum(pe['foreign_sell_mln'],1)}m.")
        else:
            out.append(f"Foreign investors were <b>net {'buyers' if n>0 else 'sellers'}</b> of {tzs_compact(abs(n)*1e6)} "
                       f"({fpct(pe['pct_buy_foreign'],0,False)} of buying, {fpct(pe['pct_sell_foreign'],0,False)} of selling was foreign).")
    bd = ds["bonds"]
    if bd["available"] and bd["total_turnover_mln"]:
        big = max(bd["by_term"], key=lambda x: x["turnover_mln"])
        out.append(f"Government bonds: <b>{tzs_compact(bd['total_turnover_mln']*1e6)}</b> face value traded in {bd['total_deals']} deals, "
                   f"mostly the {TENOR_WORDS.get(big['term'], str(big['term'])+'-year')} at an average yield of {fnum(big['wa_yield'],2)}%.")
    elif bd["available"]:
        out.append("No government bonds changed hands on the exchange.")
    return out


def indicator_meanings(ds: dict) -> dict[str, str]:
    """One-line 'what it means' per key indicator row."""
    t, p = ds["totals"], ds["prev_totals"]
    m = {}
    r = _ratio_words(t["turnover"], p.get("turnover"))
    m["turnover"] = f"The value of all shares traded. Today was {r} the previous session." if r else "The value of all shares traded today."
    m["volume"] = "How many shares changed hands. Big swings usually come from one or two large block deals."
    m["total_cap"] = "What the whole market is worth at today's prices, including the six companies also listed in Nairobi or Kampala."
    m["domestic_cap"] = "The same measure for Tanzanian-only companies — the better gauge of the local market."
    m["etf_cap"] = "Value of the two exchange-traded funds (baskets of shares that trade like a single share)."
    m["DSEI"] = "Price index of every listed company. Up means share prices rose on average."
    m["TSI"] = "Price index of the Tanzanian companies only."
    m["IA"] = "Industrial & manufacturing names such as breweries, cement and tobacco."
    m["BI"] = "Banks and financial companies — the heaviest-traded sector."
    m["CS"] = "Commercial-services companies such as telecoms and media."
    return m


def movers_text(ds: dict) -> str:
    mv = [x for x in ds["movers"] if x["code"] != "Others"]
    if not mv:
        return "No shares were traded."
    top = mv[0]
    s = (f"<b>{top['code']}</b> alone accounted for {fpct(top['share_pct'],0,False)} of everything traded today "
         f"({tzs_compact(top['turnover'])}).")
    if len(mv) > 1:
        s += f" The top {len(mv)} counters together made up {fpct(sum(x['share_pct'] for x in mv),0,False)} of turnover."
    s += " A market where a handful of names dominate trading is normal for Dar es Salaam; it also means the index can move on very few deals."
    if ds.get("block_trades"):
        s += f" {ds['block_trades']} (block trades are large pre-arranged deals between two parties, reported separately from normal trading)."
    return s


def gainers_losers_text(ds: dict) -> str:
    g, l = ds["gainers"], ds["losers"]
    parts = []
    if g:
        parts.append("Gainers: " + ", ".join(f"<b>{x['code']}</b> {fpct(x['change_pct'])} (TZS {fnum(x['prev_close'])} to {fnum(x['close'])})" for x in g) + ".")
    if l:
        parts.append("Losers: " + ", ".join(f"<b>{x['code']}</b> {fpct(x['change_pct'])} (TZS {fnum(x['prev_close'])} to {fnum(x['close'])})" for x in l) + ".")
    if not parts:
        return "No share price moved today."
    thin = [x for x in g + l if x.get("deals") is not None and x["deals"] <= 5]
    if thin:
        parts.append(f"Note: {', '.join(x['code'] for x in thin)} moved on five deals or fewer, so the change says little about broad demand.")
    parts.append("Price moves on the DSE are capped at 20% per day for most counters, and a counter that does not trade keeps its last price.")
    return " ".join(parts)


def participation_text(ds: dict) -> str:
    pe = (ds.get("participation") or {}).get("equity")
    if not pe:
        return ("Foreign-versus-local figures come from the exchange's own daily report, which had not been published when this page was built. "
                "They will appear once the report is out.")
    n = pe["net_foreign_mln"]
    s = (f"Of today's {tzs_compact(pe['total_turnover_mln']*1e6)} of share purchases, foreign investors bought {fpct(pe['pct_buy_foreign'],1,False)} "
         f"and local investors {fpct(pe['pct_buy_local'],1,False)}. On the selling side foreigners were {fpct(pe['pct_sell_foreign'],1,False)}. ")
    if n is None:
        return s
    if abs(n) < 50:
        s += "Buying and selling by foreigners nearly cancelled out, so money neither entered nor left the market from abroad in any meaningful amount."
    elif n > 0:
        s += (f"Foreigners bought {tzs_compact(n*1e6)} more than they sold — a <b>net inflow</b>. Sustained inflows tend to support prices because "
              f"foreign funds usually buy the large, liquid banks and telecoms.")
    else:
        s += (f"Foreigners sold {tzs_compact(abs(n)*1e6)} more than they bought — a <b>net outflow</b>. One day is noise; a run of outflow days "
              f"is worth watching because it weighs on the biggest counters.")
    pt = (ds.get("participation") or {}).get("etf")
    if pt and pt.get("total_turnover_mln"):
        s += f" In the ETF market ({tzs_compact(pt['total_turnover_mln']*1e6)} traded) foreign participation was {fpct(pt['pct_buy_foreign'],1,False)} of buying."
    return s


def bonds_text(ds: dict) -> str:
    bd = ds["bonds"]
    if not bd["available"]:
        return "Bond-trade details come from the exchange's daily report, which was not yet published when this page was built."
    if not bd["total_turnover_mln"]:
        return ("No government bonds traded on the exchange today. Most bond activity in Tanzania happens at the fortnightly Bank of Tanzania auctions "
                "(see below); the secondary market is thin on many days.")
    active = [b for b in bd["by_term"] if b["turnover_mln"] > 0]
    big = max(active, key=lambda x: x["turnover_mln"])
    s = (f"<b>{tzs_compact(bd['total_turnover_mln']*1e6)}</b> of government bonds (face value) changed hands in {bd['total_deals']} deals. "
         f"The {TENOR_WORDS.get(big['term'], str(big['term'])+'-year')} dominated with {fpct(big['turnover_mln']/bd['total_turnover_mln']*100,0,False)} of the value, "
         f"at a weighted average price of {fnum(big['wa_price'],1)} per 100 and a yield of {fnum(big['wa_yield'],2)}%. ")
    s += ("A price above 100 means buyers paid a premium for a bond whose coupon is higher than today's rates; the <b>yield</b> is the annual return "
          "a buyer locks in by holding to maturity, so it is the number to compare across bonds. ")
    others = [b for b in active if b is not big]
    if others:
        s += "Also traded: " + ", ".join(f"{TENOR_WORDS.get(b['term'], str(b['term'])+'-year')} ({tzs_compact(b['turnover_mln']*1e6)}, yield {fnum(b['wa_yield'],2)}%)" for b in others) + "."
    if bd.get("corporate_note"):
        s += " No corporate bonds traded."
    return s


def auction_bond_text(a: dict | None) -> str:
    if not a:
        return "Bank of Tanzania auction results were not reachable when this page was built."
    btc = a.get("bid_to_cover")
    s = (f"At the latest auction ({short_date(a['date']) if a.get('date') else 'date n/a'}) the Government re-sold its "
         f"<b>{fnum(a['coupon'],2)}% {int(a['term'])}-year bond</b> (No. {a['auction_no']}). Investors offered {tzs_compact(a['tendered_mln']*1e6)} "
         f"for the {tzs_compact(a['offered_mln']*1e6)} on sale")
    if btc:
        s += f" — demand was <b>{btc:.1f} times</b> the supply" + (", a strong auction" if btc >= 2 else ", a comfortable auction" if btc >= 1.2 else ", a soft auction")
    s += (f". Successful bidders paid an average of {fnum(a['wap'],2)} per 100 of face value, which works out to a "
          f"<b>yield of {fnum(a['way'],2)}% a year</b> to maturity. ")
    if a.get("wap") and a["wap"] > 100:
        s += "Paying above 100 is normal when the bond's coupon is higher than current market yields — the premium is what brings the return down to today's rate."
    return s


def auction_tbill_text(t: dict | None) -> str:
    if not t:
        return "Treasury-bill auction results were not reachable when this page was built."
    pairs = [(ten, y) for ten, y in zip(t["tenors"], t["way"]) if y is not None]
    if not pairs:
        return "Treasury-bill auction results were published without yields."
    s = (f"Treasury bills are the Government's short-term borrowing (35 to 364 days), sold at a discount and repaid at face value. "
         f"At auction No. {t['auction_no']}" + (f" on {short_date(t['date'])}" if t.get('date') else "") + " yields were "
         + ", ".join(f"{ten.replace(' Days','-day')} {fnum(y,2)}%" for ten, y in pairs) + ". ")
    tot_off = sum(x or 0 for x in t["offered_mln"]); tot_ten = sum(x or 0 for x in t["tendered_mln"])
    if tot_off and tot_ten:
        s += f"Across all four maturities investors bid {tzs_compact(tot_ten*1e6)} for {tzs_compact(tot_off*1e6)} offered ({tot_ten/tot_off:.1f} times)."
    return s


def cis_text(ds: dict) -> str:
    funds = ds.get("cis") or []
    if not funds:
        return "Unit-trust prices could not be collected today."
    s = ("Unit trusts (collective investment schemes) pool many investors' money; the <b>NAV per unit</b> is what one unit is worth today. "
         "Daily change shows what the unit did since the last valuation; YTD is the gain since the start of the year; the annualised column stretches YTD to a full year so funds can be compared.")
    best = max((f for f in funds if f.get("ytd_pct") is not None), key=lambda f: f["ytd_pct"], default=None)
    if best:
        s += f" Best so far this year: <b>{best['fund']}</b>, up {fpct(best['ytd_pct'],1,False)}."
    mm = [f for f in funds if any(k in f["fund"] for k in ("Liquid", "Money Market", "Faida", "Pesa"))]
    if mm:
        s += " Money-market funds move a little every day and rarely fall; equity-heavy funds such as Umoja or the Inuka Dozen Index can rise or fall with the stock market."
    s += (" YTD here is the change in the unit price alone; funds that pay income out to investors (for example UTT's Bond Fund and Jikimu Fund) "
          "show a lower unit-price gain than their total return.")
    return s


def equities_table_note(ds: dict) -> str:
    return ("<b>How to read this table.</b> Previous close and close are prices per share in TZS. Change is close versus previous close. "
            "YTD compares today's close with the last price of the previous year. Turnover is the value traded, deals the number of transactions. "
            "Bids and offers are the shares still waiting to be bought or sold at the close — many more bids than offers hints at pent-up demand. "
            "Market cap is shares in issue times price, in billions of TZS. Companies marked ‡ are cross-listed (primarily traded in Nairobi or Kampala) and rarely trade here.")


def etf_text(ds: dict) -> str:
    rows = ds.get("etfs") or []
    if not rows:
        return "No ETF data was available."
    s = ("An exchange-traded fund (ETF) is a basket of shares that trades like one share. "
         + "; ".join(f"<b>{r['code']}</b> closed at TZS {fnum(r['close'])}" + (f" ({fpct(r['change_pct'])})" if r.get('change_pct') is not None else "")
                     + (f" on {tzs_compact(r['turnover'])} of trades" if r.get('turnover') else "") for r in rows) + ".")
    return s
