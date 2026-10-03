"""Plain-language explanations generated from the numbers (rule-based, no model in the loop).

Tone: short sentences, jargon explained where it first appears, numbers rounded to what a
reader can hold in their head, descriptive rather than predictive. Every string that comes
from an outside source (counter codes, fund names, auction numbers, the exchange's own
sentences) is HTML-escaped here; the renderer inserts these strings as-is."""
from __future__ import annotations

import math
from html import escape as esc

from .util import fnum, fpct, short_date, tzs_compact

TENOR_WORDS = {2: "2-year", 5: "5-year", 7: "7-year", 10: "10-year", 15: "15-year", 20: "20-year", 25: "25-year"}
THIN_TURNOVER = 5_000_000  # TZS; below this a price move says little about demand


def tenor(term) -> str:
    try:
        return TENOR_WORDS.get(int(term), f"{int(term)}-year")
    except (TypeError, ValueError):
        return "bond"


def plural(n, one, many=None) -> str:
    n = int(n or 0)
    return f"{n:,} {one if n == 1 else (many or one + 's')}"


def _ratio_words(new, old):
    """'about a third of', 'about 3 times', '20% less than', 'about the same as'."""
    if not new or not old or old <= 0 or new <= 0:
        return None
    r = new / old
    if r >= 1.8:
        frac = r % 1
        if frac >= 0.85:
            return f"almost {math.ceil(r)} times"
        if frac <= 0.15:
            return f"about {math.floor(r)} times"
        return f"about {r:.1f} times"
    if r >= 1.08:
        return f"{(r - 1) * 100:.0f}% more than"
    if r >= 0.92:
        return "about the same as"
    if r >= 0.58:
        return f"{(1 - r) * 100:.0f}% less than"
    if r >= 0.42:
        return "about half of"
    if r >= 0.29:
        return "about a third of"
    if r >= 0.22:
        return "about a quarter of"
    return f"only {r * 100:.0f}% of"


def flow_state(pe: dict | None) -> str | None:
    """'in' / 'out' / 'flat' judged relative to the day's turnover, or None when unknown."""
    if not pe or pe.get("net_foreign_mln") is None:
        return None
    net, total = pe["net_foreign_mln"], pe.get("total_turnover_mln") or 0
    threshold = max(25.0, 0.02 * total)
    if abs(net) < threshold:
        return "flat"
    return "in" if net > 0 else "out"


def _index_phrase(i: dict) -> str:
    """'fell 0.3% to 4,639.96' / 'closed flat at 4,639.96'."""
    pct = i.get("change_pct")
    if pct is None or abs(pct) < 0.005:
        return f"closed flat at {fnum(i['close'], 2)}"
    return f"{'rose' if pct > 0 else 'fell'} {fpct(abs(pct), sign=False)} to {fnum(i['close'], 2)}"


def _mover_phrase(x: dict) -> str:
    s = f"<b>{esc(x['code'])}</b> {fpct(x['change_pct'])} to TZS {fnum(x['close'])}"
    if x.get("volume") and (x.get("turnover") or 0) < THIN_TURNOVER:
        s += f" on thin trading ({tzs_compact(x['turnover'])})"
    elif x.get("turnover"):
        s += f" ({tzs_compact(x['turnover'])} traded)"
    return s


def summary_bullets(ds: dict) -> list[str]:
    """The 'today in one minute' list."""
    t, p = ds["totals"], ds.get("prev_totals") or {}
    out = []
    if not t.get("turnover"):
        out.append("<b>No shares were traded</b> on the exchange in this session.")
    else:
        ratio = _ratio_words(t["turnover"], p.get("turnover"))
        deals = f" in {plural(t['deals'], 'deal')}" if t.get("deals") else ""
        if ratio:
            out.append(f"<b>{tzs_compact(t['turnover'])}</b> worth of shares changed hands{deals} — "
                       f"{ratio} the {tzs_compact(p['turnover'])} traded the previous session.")
        else:
            out.append(f"<b>{tzs_compact(t['turnover'])}</b> worth of shares changed hands{deals}.")
    idx = {i["code"]: i for i in ds["indices"]}
    dsei, tsi = idx.get("DSEI"), idx.get("TSI")
    if dsei:
        pct = dsei.get("change_pct")
        lead = "were little changed" if pct is None or abs(pct) < 0.005 else ("rose" if pct > 0 else "fell")
        s = f"Prices overall <b>{lead}</b>: the All Share Index (DSEI) {_index_phrase(dsei)}"
        if tsi:
            s += f"; the local-companies index (TSI) {_index_phrase(tsi)}"
        out.append(s + ".")
    b = ds["breadth"]
    if b.get("traded"):
        s = (f"Of the {plural(b['traded'], 'counter')} that traded, <b>{b['advancers']} closed higher, {b['decliners']} lower</b> "
             f"and {b['unchanged']} {'was' if b['unchanged'] == 1 else 'were'} unchanged")
        if b.get("not_traded"):
            s += f"; {b['not_traded']} did not trade"
        out.append(s + " (a counter is one listed company's shares).")
    g, l = ds["gainers"], ds["losers"]
    if g or l:
        parts = []
        if g:
            parts.append("Best performer: " + _mover_phrase(g[0]))
        if l:
            parts.append("Weakest: " + _mover_phrase(l[0]))
        out.append(". ".join(parts) + ".")
    elif t.get("turnover"):
        out.append("No traded share changed price.")
    pe = (ds.get("participation") or {}).get("equity")
    st = flow_state(pe)
    if st == "flat":
        out.append(f"Foreign investors were roughly <b>balanced</b>: they bought {tzs_compact(pe['foreign_buy_mln'] * 1e6)} "
                   f"and sold {tzs_compact(pe['foreign_sell_mln'] * 1e6)}.")
    elif st:
        n = pe["net_foreign_mln"]
        out.append(f"Foreign investors were <b>net {'buyers' if n > 0 else 'sellers'}</b> of {tzs_compact(abs(n) * 1e6)} "
                   f"({fpct(pe['pct_buy_foreign'], 0, False)} of buying and {fpct(pe['pct_sell_foreign'], 0, False)} of selling was foreign).")
    bd = ds["bonds"]
    if bd["available"] and bd["total_turnover_mln"]:
        big = max(bd["by_term"], key=lambda x: x["turnover_mln"])
        share = big["turnover_mln"] / bd["total_turnover_mln"] * 100
        lead = "all of it the" if share >= 99 else "mostly the" if share >= 50 else "led by the"
        out.append(f"Government bonds: <b>{tzs_compact(bd['total_turnover_mln'] * 1e6)}</b> face value traded in {plural(bd['total_deals'], 'deal')}, "
                   f"{lead} {tenor(big['term'])} at an average yield of {fnum(big['wa_yield'], 2)}%.")
    elif bd["available"]:
        out.append("No government bonds changed hands on the exchange.")
    return out


def indicator_meanings(ds: dict) -> dict[str, str]:
    """One-line 'what it means' per key indicator row."""
    t, p = ds["totals"], ds.get("prev_totals") or {}
    n_cross = sum(1 for e in ds["equities"] if e.get("cross_listed"))
    n_etf = len(ds.get("etfs") or [])
    m = {}
    r = _ratio_words(t.get("turnover"), p.get("turnover"))
    m["turnover"] = f"The value of all shares traded. This session was {r} the previous one." if r else "The value of all shares traded in the session."
    m["volume"] = "How many shares changed hands. A large jump often comes from one or two big block deals rather than broad activity."
    m["deals"] = "Completed transactions. Many deals with low turnover usually points to small retail orders; few deals with high turnover points to large blocks."
    m["total_cap"] = (f"What the whole market is worth at today's prices, including the {n_cross} Kenyan companies whose main listing is in Nairobi."
                      if n_cross else "What the whole market is worth at today's prices.")
    m["domestic_cap"] = "The same measure for Tanzanian companies only — the better gauge of the local market."
    m["etf_cap"] = f"Value of the {plural(n_etf, 'exchange-traded fund')} (baskets of shares that trade like a single share)."
    m["DSEI"] = "Price index of every listed company. Up means share prices rose on average."
    m["TSI"] = "Price index of the Tanzanian companies only."
    m["IA"] = "Industrial and manufacturing names such as breweries, cement and tobacco."
    m["BI"] = "Banks and other financial companies."
    m["CS"] = "Commercial-services companies such as telecoms and media."
    return m


def movers_text(ds: dict) -> str:
    mv = [x for x in ds["movers"] if x["code"] != "Others"]
    if not mv or not ds["totals"].get("turnover"):
        return "No shares were traded."
    top = mv[0]
    s = (f"<b>{esc(top['code'])}</b> alone accounted for {fpct(top['share_pct'], 0, False)} of all share trading in the session "
         f"({tzs_compact(top['turnover'])}).")
    if len(mv) > 1:
        s += f" The top {len(mv)} counters together made up {fpct(sum(x['share_pct'] for x in mv), 0, False)} of share turnover."
    s += " Trading on the DSE is usually concentrated in a handful of names, which also means the index can move on very few deals."
    if ds.get("block_trades"):
        s += (f" The exchange also reported block trades — large pre-arranged deals between two parties, crossed on a separate board: "
              f"{esc(ds['block_trades']).replace('On the block-trade board, ', '')}.")
    return s


def gainers_losers_text(ds: dict) -> str:
    g, l = ds["gainers"], ds["losers"]
    parts = []
    if g:
        parts.append("Gainers: " + ", ".join(f"<b>{esc(x['code'])}</b> {fpct(x['change_pct'])} (TZS {fnum(x['prev_close'])} to {fnum(x['close'])})" for x in g) + ".")
    if l:
        parts.append("Losers: " + ", ".join(f"<b>{esc(x['code'])}</b> {fpct(x['change_pct'])} (TZS {fnum(x['prev_close'])} to {fnum(x['close'])})" for x in l) + ".")
    if not parts:
        return "No traded share changed price in this session."
    thin = [x for x in g + l if x.get("deals") is not None and 0 < x["deals"] <= 5 or (x.get("turnover") or 0) < THIN_TURNOVER]
    if thin:
        parts.append(f"Note: {', '.join(esc(x['code']) for x in thin)} moved on very little trading (five deals or fewer, or under TZS 5 million), "
                     f"so the change says little about broad demand.")
    cross = [e for e in ds.get("cross_moves") or []]
    if cross:
        parts.append("Cross-listed Kenyan companies that did not trade here but whose DSE price followed their Nairobi close: "
                     + ", ".join(f"{esc(e['code'])} {fpct(e['change_pct'])}" for e in cross) + ".")
    parts.append("A counter that does not trade keeps its last DSE price; the exchange also limits how far a price may move in one session.")
    return " ".join(parts)


def participation_text(ds: dict) -> str:
    pe = (ds.get("participation") or {}).get("equity")
    if not pe:
        return ("Foreign-versus-local figures come from the exchange's own daily report, which had not been published when this page was built. "
                "They will appear once the report is out.")
    if not pe.get("total_turnover_mln"):
        return "There was no share trading, so there is no foreign-versus-local split to report."
    s = (f"Of the {tzs_compact(pe['total_turnover_mln'] * 1e6)} of share purchases, foreign investors accounted for {fpct(pe['pct_buy_foreign'], 1, False)} "
         f"and local investors for {fpct(pe['pct_buy_local'], 1, False)}. Foreigners accounted for {fpct(pe['pct_sell_foreign'], 1, False)} of selling. ")
    st = flow_state(pe)
    n = pe.get("net_foreign_mln")
    if st == "flat":
        s += "Foreign buying and selling roughly balanced, so little money entered or left the market from abroad on the day."
    elif st == "in":
        s += f"Foreigners bought {tzs_compact(n * 1e6)} more than they sold — a <b>net inflow</b>: money came into the market from abroad on the day."
    elif st == "out":
        s += f"Foreigners sold {tzs_compact(abs(n) * 1e6)} more than they bought — a <b>net outflow</b>: money left the market on the day."
    pt = (ds.get("participation") or {}).get("etf")
    if pt and pt.get("total_turnover_mln"):
        if (pt.get("pct_buy_foreign") or 0) == 0:
            s += f" In the ETF market ({tzs_compact(pt['total_turnover_mln'] * 1e6)} traded) all buying was local."
        else:
            s += f" In the ETF market ({tzs_compact(pt['total_turnover_mln'] * 1e6)} traded) foreigners accounted for {fpct(pt['pct_buy_foreign'], 1, False)} of buying."
    return s


def bonds_text(ds: dict) -> str:
    bd = ds["bonds"]
    if not bd["available"]:
        return "Bond-trade details come from the exchange's daily report, which was not yet published when this page was built."
    if not bd["total_turnover_mln"]:
        s = ("No government bonds traded on the exchange in this session. That happens from time to time: bonds are first sold at Bank of Tanzania "
             "auctions (results below) and then change hands on the DSE, where activity varies a lot from day to day.")
        if bd.get("other_bonds"):
            s += " " + _other_bonds_sentence(bd)
        return s
    active = [b for b in bd["by_term"] if b["turnover_mln"] > 0]
    big = max(active, key=lambda x: x["turnover_mln"])
    share = big["turnover_mln"] / bd["total_turnover_mln"] * 100
    opener = (f"All of it was the {tenor(big['term'])}" if share >= 99 else
              f"The {tenor(big['term'])} made up {fpct(share, 0, False)} of the value" if share >= 50 else
              f"The largest share, {fpct(share, 0, False)}, was the {tenor(big['term'])}")
    s = (f"<b>{tzs_compact(bd['total_turnover_mln'] * 1e6)}</b> of government bonds (face value) changed hands in {plural(bd['total_deals'], 'deal')}. "
         f"{opener}, at a weighted average price of {fnum(big['wa_price'], 1)} per 100 and a yield of {fnum(big['wa_yield'], 2)}%. ")
    s += ("The <b>yield</b> is the annual return a buyer locks in by holding the bond to maturity, so it is the number to compare across bonds. "
          "Exchange prices include interest built up since the last coupon payment; the <b>clean price</b> column strips that out, and it is the clean "
          "price that shows whether a bond changed hands above (premium) or below (discount) its face value of 100. ")
    others = [b for b in active if b is not big]
    if others:
        s += "Also traded: " + ", ".join(f"{tenor(b['term'])} ({tzs_compact(b['turnover_mln'] * 1e6)}, yield {fnum(b['wa_yield'], 2)}%)" for b in others) + "."
    if bd.get("other_bonds"):
        s += " " + _other_bonds_sentence(bd)
    elif bd.get("corporate_note"):
        s += " No corporate bonds traded."
    return s


def _other_bonds_sentence(bd: dict) -> str:
    ob = bd["other_bonds"]
    return ("Other listed bonds (infrastructure or corporate) also traded: "
            + ", ".join(f"{esc(x['bond_no'])} ({tzs_compact((x.get('amount_bn') or 0) * 1e9)} at {fnum(x.get('price'), 2)}, yield {fnum(x.get('yield'), 2)}%)" for x in ob)
            + "; they are listed separately from the Treasury bonds above.")


def auction_bond_text(a: dict | None) -> str:
    if not a:
        return "Bank of Tanzania auction results were not reachable when this page was built."
    btc = a.get("bid_to_cover")
    try:
        further = int(a.get("sale_no") or 1) > 1
    except ValueError:
        further = False
    s = (f"At the latest auction ({short_date(a['date']) if a.get('date') else 'date not published'}) the Government sold "
         f"{'a further batch of' if further else ''} its <b>{fnum(a['coupon'], 2)}% {tenor(a['term'])} bond</b> (No. {esc(str(a['auction_no']))}). "
         f"Investors bid {tzs_compact(a['tendered_mln'] * 1e6)} for the {tzs_compact(a['offered_mln'] * 1e6)} on offer")
    if btc:
        s += f" — <b>{btc:.1f} times</b> the amount available, so the auction was " + (
            "comfortably covered" if btc >= 1.5 else "fully covered" if btc >= 1.0 else "not fully covered")
    s += (f". Successful bidders paid an average of {fnum(a['wap'], 2)} per 100 of face value, which works out to a "
          f"<b>yield of {fnum(a['way'], 2)}% a year</b> to maturity.")
    if a.get("wap") and a["wap"] > 100.5:
        s += (" Paying more than 100 is normal when the bond's fixed coupon is above today's market yields: the premium is what brings "
              "the buyer's return down to the market rate.")
    elif a.get("wap") and a["wap"] < 99.5:
        s += " Paying less than 100 means the bond's fixed coupon is below today's market yields; the discount tops the return up to the market rate."
    return s


def auction_tbill_text(t: dict | None) -> str:
    if not t:
        return "Treasury-bill auction results were not reachable when this page was built."
    pairs = [(ten, y) for ten, y in zip(t["tenors"], t["way"]) if y is not None]
    if not pairs:
        return "Treasury-bill auction results were published without yields."
    s = ("Treasury bills are the Government's short-term borrowing (35 to 364 days). Buyers pay less than the face value and are repaid the full "
         f"face value at maturity; the difference is their interest, shown here as a yearly yield. At auction No. {esc(str(t['auction_no']))}"
         + (f" on {short_date(t['date'])}" if t.get("date") else "") + " yields were "
         + ", ".join(f"{esc(str(ten)).replace(' Days', '-day')} {fnum(y, 2)}%" for ten, y in pairs) + ". ")
    tot_off = sum(x or 0 for x in t["offered_mln"])
    tot_ten = sum(x or 0 for x in t["tendered_mln"])
    if tot_off and tot_ten:
        s += (f"Across the {plural(len(pairs), 'maturity', 'maturities')} offered, investors bid {tzs_compact(tot_ten * 1e6)} for "
              f"{tzs_compact(tot_off * 1e6)} on offer ({tot_ten / tot_off:.1f} times).")
    return s


def cis_text(ds: dict) -> str:
    funds = ds.get("cis") or []
    if not funds:
        return "Unit-trust prices could not be collected today."
    s = ("Unit trusts (collective investment schemes) pool many investors' money; the <b>NAV per unit</b> is what one unit was worth at the fund's "
         "latest valuation (see the Valued column). Daily is the change since the previous valuation; YTD is the change in the unit price since the "
         "start of the year; Annualised stretches YTD to a full year so funds can be compared, and is shown only once a month of the year has passed.")
    with_ytd = [f for f in funds if f.get("ytd_pct") is not None]
    if with_ytd:
        best = max(with_ytd, key=lambda f: f["ytd_pct"])
        if best["ytd_pct"] > 0:
            s += f" Largest unit-price gain so far this year: <b>{esc(best['fund'])}</b>, {fpct(best['ytd_pct'], 1)}."
    s += (" Money-market funds usually move a little every day; funds that hold shares, such as Umoja or the Inuka Dozen Index, rise and fall with the "
          "stock market. YTD here is the unit price alone: funds that pay income out to investors show a lower unit-price gain than their total return.")
    return s


def equities_table_note(ds: dict) -> str:
    return ("<b>How to read this table.</b> Previous close and close are prices per share in TZS. Change is close versus previous close. "
            "YTD compares the close with the last price of the previous year (adjusted for share splits). Turnover is the value traded, deals the number "
            "of transactions. Bids and offers are the shares still waiting to be bought or sold at the close. Market cap is shares in issue times price, "
            "in billions of TZS. Companies marked ‡ are cross-listed: their main listing is on the Nairobi Securities Exchange, they rarely trade here, "
            "and their DSE price follows their Nairobi close.")


def etf_text(ds: dict) -> str:
    rows = ds.get("etfs") or []
    if not rows:
        return "No ETF data was available."
    bits = []
    for r in rows:
        b = f"<b>{esc(str(r['code']))}</b> closed at TZS {fnum(r.get('close'))}"
        if r.get("change_pct") is not None:
            b += f" ({fpct(r['change_pct'])})"
        b += f" on {tzs_compact(r['turnover'])} of trades" if r.get("turnover") else " with no trades"
        bits.append(b)
    return "An exchange-traded fund (ETF) is a basket of shares that trades like one share. " + "; ".join(bits) + "."


def trend_text(ds: dict) -> str:
    """One paragraph on the last 30 sessions, from the stored history."""
    hist = [h for h in (ds.get("history") or []) if h.get("date")]
    if len(hist) < 3:
        return "The trend charts fill in as the report builds up a history of sessions."
    first, last = hist[0], hist[-1]
    from .util import parse_iso, short_date  # noqa: PLC0415
    span = f"{short_date(parse_iso(first['date']))} to {short_date(parse_iso(last['date']))}"
    parts = [f"Over the {len(hist)} sessions from {span}:"]
    for key, name in (("dsei", "the All Share Index (DSEI)"), ("tsi", "the Tanzania Share Index (TSI)")):
        a, b = first.get(key), last.get(key)
        if a and b:
            pct = (b / a - 1) * 100
            parts.append(f"{name} {'rose' if pct > 0.05 else 'fell' if pct < -0.05 else 'was flat'}"
                         + (f" {fpct(abs(pct), 1, False)}" if abs(pct) >= 0.05 else "") + f", from {fnum(a, 2)} to {fnum(b, 2)};")
    turns = [h["turnover"] for h in hist if h.get("turnover")]
    if turns:
        avg = sum(turns) / len(turns)
        hi = max(hist, key=lambda h: h.get("turnover") or 0)
        rel = _ratio_words(last.get("turnover"), avg)
        parts.append(f"equity turnover averaged {tzs_compact(avg)} a session, with the busiest day on {short_date(parse_iso(hi['date']))} "
                     f"({tzs_compact(hi['turnover'])}). This session was {rel} the average." if rel else
                     f"equity turnover averaged {tzs_compact(avg)} a session.")
    s = " ".join(parts).replace(";.", ".")
    if s.endswith(";"):
        s = s[:-1] + "."
    return s + " Rebasing both indices to 100 at the start of the window makes their percentage moves directly comparable even though their levels differ."
