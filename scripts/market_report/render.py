"""HTML renderer — The Ticker's warm editorial design (espresso masthead, nude body,
Poppins wordmark, IBM Plex text), laid out so the same page prints cleanly to A4."""
from __future__ import annotations

from html import escape as _e

from . import charts, narrative as N
from .util import fnum, fpct, human_date, parse_iso, short_date, tiny_date, tzs_compact

SITE = "https://thetickertz.github.io/The-Ticker/"

CSS = r"""
:root{
  --page:#efe5d8; --card:#faf5ee; --card2:#f1e8db; --card3:#e9ddcc;
  --ink:#2b2119; --ink2:#6b5c4a; --muted:#8f7e69;
  --grid:#e4d8c7; --border:rgba(59,42,28,.14); --border2:rgba(59,42,28,.28);
  --up:#0e7a4a; --down:#bc3327; --up-dim:rgba(14,122,74,.12); --down-dim:rgba(188,51,39,.12);
  --s1:#2a78d6; --s1-soft:#86b6ef; --s2:#eb6834; --neutral:#b9ab97; --band:rgba(59,42,28,.06);
  --mast:#2c2015; --mast2:#3a2b1c; --mast-ink:#f8f2e9; --mast-ink2:#c9b8a2; --mast-border:rgba(248,242,233,.14);
  --sans:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
  --brand:"Poppins",var(--sans);
  --maxw:1120px; --r:10px;
}
*{box-sizing:border-box}
@media (prefers-reduced-motion:no-preference){ html{scroll-behavior:smooth} }
.sr-only{position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap; border:0}
body{background:var(--page); color:var(--ink); font-family:var(--sans); font-size:15px; line-height:1.55; margin:0; -webkit-font-smoothing:antialiased}
a{color:var(--s1)}
.mast{background:linear-gradient(160deg,var(--mast2) 0%,var(--mast) 70%); color:var(--mast-ink)}
.mast-in{max-width:var(--maxw); margin:0 auto; padding:30px 24px 18px; display:flex; flex-wrap:wrap; align-items:flex-end; justify-content:space-between; gap:18px}
.wordmark{display:flex; flex-direction:column; line-height:1; text-decoration:none; color:inherit}
.wordmark .the{font-family:var(--brand); font-weight:500; font-size:14px; letter-spacing:.52em; margin:0 0 2px 5px}
.wordmark .tick{font-family:var(--brand); font-weight:800; font-size:56px; letter-spacing:-.02em; display:flex; align-items:baseline; gap:12px}
.wordmark .tris{display:inline-flex; gap:6px; align-items:baseline}
.wordmark svg{display:block}
.mast-meta{text-align:right; font-family:var(--mono); font-size:12.5px; color:var(--mast-ink2)}
.mast-meta .tag{display:inline-block; border:1px solid var(--mast-border); border-radius:999px; padding:3px 12px; margin-bottom:8px; color:var(--mast-ink); font-size:11px; letter-spacing:.08em}
.mast-meta h1{font-family:var(--sans); font-size:22px; font-weight:700; color:var(--mast-ink); margin:2px 0 4px; letter-spacing:-.01em}
.mast-meta .asof b{color:var(--mast-ink); font-weight:600}
.tape{border-top:1px solid var(--mast-border); background:#241a11; overflow:hidden}
.tape-track{display:flex; width:max-content; animation:tape 80s linear infinite}
.tape:hover .tape-track{animation-play-state:paused}
@keyframes tape{from{transform:translateX(0)}to{transform:translateX(-50%)}}
@media (prefers-reduced-motion:reduce){ .tape{overflow-x:auto} .tape-track{animation:none; width:auto} }
.tape-item{display:flex; align-items:center; gap:8px; padding:9px 20px; border-right:1px solid var(--mast-border); font-family:var(--mono); font-size:12.5px; white-space:nowrap}
.tape-item .tl{color:var(--mast-ink2); letter-spacing:.05em} .tape-item .tv{color:var(--mast-ink); font-weight:600}
.tri{width:0; height:0; display:inline-block}
.tri.up{border-left:5px solid transparent; border-right:5px solid transparent; border-bottom:8px solid var(--up)}
.tri.dn{border-left:5px solid transparent; border-right:5px solid transparent; border-top:8px solid var(--down)}
.tri.fl{width:8px; height:2px; background:var(--muted); border:0}
.tape .tri.up{border-bottom-color:#2fce85} .tape .tri.dn{border-top-color:#ff6b5e} .tape .tri.fl{background:var(--mast-ink2)}
.nav{position:sticky; top:0; z-index:40; background:rgba(44,32,21,.95); backdrop-filter:blur(10px); border-bottom:1px solid var(--mast-border)}
.nav-in{max-width:var(--maxw); margin:0 auto; padding:0 16px; display:flex; gap:2px; overflow-x:auto}
.nav a{color:var(--mast-ink2); text-decoration:none; font-size:13px; font-weight:500; padding:11px 12px; white-space:nowrap; border-bottom:2px solid transparent}
.nav a:hover{color:var(--mast-ink)} .nav a.tool{color:var(--mast-ink); font-weight:600}
main{max-width:var(--maxw); margin:0 auto; padding:10px 24px 50px}
main > section{border-top:2px solid rgba(59,42,28,.18); margin-top:40px; padding-top:30px; scroll-margin-top:56px}
main > section:first-of-type{border-top:0; margin-top:0; padding-top:28px}
.sec-head{display:flex; align-items:baseline; gap:14px; flex-wrap:wrap; margin-bottom:6px}
.sec-head h2{font-size:23px; font-weight:700; letter-spacing:-.01em; margin:0}
.sec-head .kicker{font-family:var(--mono); font-size:11px; letter-spacing:.14em; color:var(--muted); text-transform:uppercase}
.sec-head .kicker b{color:var(--s1); font-weight:600; margin-right:6px}
.sec-lede{color:var(--ink2); max-width:72ch; margin:0 0 18px}
.sec-lede b, .plain b, .bullets b{color:var(--ink); font-weight:600}
.grid{display:grid; gap:14px} .grid > *, .two > *, .pair > *{min-width:0}
.pair{display:grid; gap:14px}
.tape-wrap{position:relative} .tape-pause{position:absolute; right:8px; top:6px; z-index:2; font-family:var(--mono); font-size:11px; color:var(--mast-ink); background:rgba(36,26,17,.85); border:1px solid var(--mast-border); border-radius:999px; padding:3px 10px; cursor:pointer}
.tape.paused .tape-track{animation-play-state:paused}
.sharebars{display:grid; grid-template-columns:auto 1fr auto; gap:8px 12px; align-items:center; font-family:var(--mono); font-size:12.5px; margin-top:6px}
.sharebars .lb{font-weight:600; color:var(--ink)} .sharebars .bar{height:16px; border-radius:0 4px 4px 0; background:var(--s1-soft)} .sharebars .bar.top{background:var(--s1)} .sharebars .bar.other{background:var(--neutral)}
.sharebars .vl{color:var(--ink2); white-space:nowrap}
.grid.c4{grid-template-columns:repeat(4,1fr)} .grid.c3{grid-template-columns:repeat(3,1fr)} .grid.c2{grid-template-columns:repeat(2,1fr)}
.grid.c2w{grid-template-columns:1.15fr 1fr}
@media (max-width:900px){ .grid.c4{grid-template-columns:repeat(2,1fr)} .grid.c3{grid-template-columns:repeat(2,1fr)} .grid.c2w{grid-template-columns:1fr} }
@media (max-width:560px){ .grid.c4,.grid.c3,.grid.c2{grid-template-columns:1fr} .wordmark .tick{font-size:44px} .mast-meta{text-align:left} }
.card{background:var(--card); border:1px solid var(--border); border-radius:var(--r); padding:16px 18px}
.tile .lbl{font-size:12.5px; font-weight:600; color:var(--ink2); letter-spacing:.02em}
.tile .val{font-size:30px; font-weight:700; letter-spacing:-.01em; margin:4px 0 2px; display:flex; align-items:baseline; gap:10px; flex-wrap:wrap}
.tile .val .unit{font-size:14px; color:var(--muted); font-weight:500}
.tile .sub{font-size:12px; font-family:var(--mono); color:var(--muted)}
.tile .spark{margin-top:8px}
.delta{display:inline-flex; align-items:center; gap:5px; font-family:var(--mono); font-size:12px; font-weight:600; border-radius:999px; padding:2px 9px}
.delta.up{color:var(--up); background:var(--up-dim)} .delta.dn{color:var(--down); background:var(--down-dim)} .delta.fl{color:var(--ink2); background:var(--band)}
.plain{font-size:13.5px; color:var(--ink2); margin-top:10px; padding-top:10px; border-top:1px solid var(--border)}
.bullets{margin:0; padding-left:20px; color:var(--ink2); display:grid; gap:7px; font-size:14.5px}
.chart-card{background:var(--card); border:1px solid var(--border); border-radius:var(--r); padding:16px 18px 10px}
.chart-head{display:flex; justify-content:space-between; align-items:flex-start; gap:14px; flex-wrap:wrap}
.chart-head h3{font-size:15px; font-weight:600; margin:0} .chart-head .note{font-size:12.5px; color:var(--muted); margin:2px 0 0}
.legend{display:flex; gap:14px; font-size:12.5px; color:var(--ink2); align-items:center; flex-wrap:wrap}
.legend .li{display:inline-flex; align-items:center; gap:7px} .legend .key{width:14px; height:10px; border-radius:2px; display:inline-block}
.chart-host{margin-top:10px}
.empty{font-size:13px; color:var(--muted); padding:30px 0; text-align:center}
table.data{border-collapse:collapse; width:100%; font-family:var(--mono); font-size:12.5px; font-variant-numeric:tabular-nums}
table.data th{color:var(--muted); font-weight:500; text-align:right; padding:7px 10px 7px 0; border-bottom:1px solid var(--border2); letter-spacing:.04em; font-size:10.5px; text-transform:uppercase; font-family:var(--sans); white-space:nowrap}
table.data td{padding:6px 10px 6px 0; border-bottom:1px solid var(--grid); color:var(--ink2); text-align:right; white-space:nowrap}
table.data th:first-child, table.data td:first-child{text-align:left} table.data td:first-child{color:var(--ink); font-weight:600}
table.data th.l, table.data td.l{text-align:left; white-space:normal}
table.data tr.total td{border-top:1px solid var(--border2); font-weight:600; color:var(--ink)}
table.data tbody tr:nth-child(even) td{background:rgba(59,42,28,.028)}
table.data tbody tr:hover td{background:rgba(42,120,214,.07)}
.dbar{display:block; height:3px; border-radius:2px; background:var(--s1-soft); margin:3px 0 0 auto; min-width:4px}
.chart-host{position:relative}
@media (max-width:700px){ .chart-host.scroll{overflow-x:auto; -webkit-overflow-scrolling:touch} .chart-host.scroll svg{min-width:560px} }
.tip{position:absolute; pointer-events:none; background:#fffdf9; border:1px solid var(--border2); border-radius:8px; padding:8px 11px; font-size:12.5px; box-shadow:0 10px 28px rgba(59,42,28,.22); opacity:0; transition:opacity .12s; min-width:150px; max-width:240px; z-index:5}
@media (prefers-reduced-motion:reduce){ .tip{transition:none} }
.tip .tt{font-family:var(--mono); font-size:11px; color:var(--muted); margin-bottom:5px}
.tip .trow{display:flex; align-items:baseline; gap:8px} .tip .tkey{width:12px; height:3px; border-radius:2px; flex:none; align-self:center}
.tip .tval{font-family:var(--mono); font-weight:600; font-size:13.5px; color:var(--ink)} .tip .tname{color:var(--ink2); font-size:11.5px}
.tschart:focus-visible{outline:2px solid var(--s1); outline-offset:2px; border-radius:6px}
.chart-foot{font-size:11.5px; color:var(--muted); padding:6px 0 4px}
.mast-meta .issue{display:inline-block; font-family:var(--mono); font-size:11px; letter-spacing:.08em; color:var(--mast-ink2); margin-left:8px}
.cover{display:none}
table.data td.meaning{font-family:var(--sans); color:var(--ink2); font-size:12.5px; white-space:normal; min-width:200px}
.up{color:var(--up)} .dn{color:var(--down)} .fl{color:var(--muted)}
td.chg{font-weight:600}
.twrap{overflow-x:auto}
.two{display:grid; grid-template-columns:1fr 1fr; gap:14px}
@media (max-width:760px){ .two{grid-template-columns:1fr} }
.auction{display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-top:12px}
@media (max-width:760px){ .auction{grid-template-columns:repeat(2,1fr)} }
.auction .ts{background:var(--card2); border:1px solid var(--border); border-radius:8px; padding:10px 12px}
.auction .ts .k{font-size:10.5px; color:var(--muted); text-transform:uppercase; letter-spacing:.06em}
.auction .ts .v{font-family:var(--mono); font-size:16px; font-weight:600; color:var(--ink); margin-top:3px}
.gloss{columns:2; column-gap:28px; margin-top:6px} @media (max-width:760px){ .gloss{columns:1} }
.gloss .g{break-inside:avoid; padding:10px 0; border-bottom:1px solid var(--border)}
.gloss dt{font-weight:600; font-size:13.5px} .gloss dd{margin:3px 0 0; font-size:12.5px; color:var(--ink2)}
footer{margin-top:50px; background:var(--mast); color:var(--mast-ink2)}
.foot-in{max-width:var(--maxw); margin:0 auto; padding:26px 24px 34px; display:grid; grid-template-columns:1.2fr 1fr; gap:28px; font-size:13px}
@media (max-width:760px){ .foot-in{grid-template-columns:1fr} }
footer h4{font-size:12px; text-transform:uppercase; letter-spacing:.1em; color:var(--mast-ink); margin:0 0 10px; opacity:.85}
footer a{color:var(--mast-ink2)} footer ul{margin:0; padding-left:18px} footer li{margin-bottom:5px}
.foot-bar{border-top:1px solid var(--mast-border); padding:14px 24px 18px; text-align:center; font-family:var(--mono); font-size:11.5px}
.foot-bar b{color:var(--mast-ink); font-weight:600}
.notes{font-size:12.5px; color:var(--ink2); background:var(--card2); border:1px dashed var(--border2); border-radius:8px; padding:10px 14px; margin-top:14px}
.disclaimer{font-size:12.5px; color:var(--ink2); border:1px dashed var(--border2); border-radius:8px; padding:12px 16px; margin-top:16px}
.actions{display:flex; gap:10px; flex-wrap:wrap; margin-top:10px}
.btn{display:inline-flex; align-items:center; gap:8px; font-family:var(--mono); font-size:12px; font-weight:600; letter-spacing:.04em; color:var(--mast); background:var(--mast-ink); border-radius:999px; padding:7px 14px; text-decoration:none}
.btn.ghost{background:transparent; color:var(--mast-ink); border:1px solid var(--mast-border)}
.foot-note{font-family:var(--mono); font-size:11.5px; opacity:.8; margin-top:12px}
@media print{
  @page{size:A4; margin:12mm 11mm 14mm}
  body{background:#fff; font-size:11.5px; line-height:1.4}
  .nav, .tape, .tape-wrap, .actions, .screen-only, .tip, .mast{display:none !important}
  .cover{display:flex; flex-direction:column; justify-content:space-between; min-height:252mm; break-after:page; background:linear-gradient(160deg,var(--mast2) 0%,var(--mast) 70%); color:var(--mast-ink); border-radius:8px; padding:26mm 18mm 16mm; -webkit-print-color-adjust:exact; print-color-adjust:exact}
  .cover .wordmark .the{font-size:16px} .cover .wordmark .tick{font-size:64px}
  .cover .ctag{font-family:var(--mono); font-size:11px; letter-spacing:.16em; color:var(--mast-ink2); margin-top:34px}
  .cover h1{font-size:34px; font-weight:700; margin:8px 0 4px; letter-spacing:-.01em; color:var(--mast-ink)}
  .cover .cdate{font-size:19px; color:var(--mast-ink2); margin:0 0 30px}
  .cover .heroes{display:grid; grid-template-columns:repeat(2,1fr); gap:12px}
  .cover .hero{border:1px solid var(--mast-border); border-radius:10px; padding:12px 14px}
  .cover .hero .k{font-family:var(--mono); font-size:10px; letter-spacing:.1em; color:var(--mast-ink2); text-transform:uppercase}
  .cover .hero .v{font-size:26px; font-weight:700; margin-top:4px; color:var(--mast-ink)} .cover .hero .d{font-family:var(--mono); font-size:11px; color:var(--mast-ink2); margin-top:2px}
  .cover .inside{margin-top:26px; font-size:12px; color:var(--mast-ink2); columns:2; column-gap:24px} .cover .inside b{color:var(--mast-ink); display:block; margin-bottom:6px; font-size:11px; letter-spacing:.12em}
  .cover .inside ol{margin:0; padding-left:18px} .cover .inside li{margin-bottom:3px}
  .cover .cfoot{font-family:var(--mono); font-size:10px; color:var(--mast-ink2); border-top:1px solid var(--mast-border); padding-top:10px; margin-top:20px; line-height:1.6}
  .cover .heroes .hero .v{color:var(--mast-ink)} .cover .tri{display:none}
  main{padding:0 0 10px; max-width:none} main > section{margin-top:18px; padding-top:14px; border-top-width:1px}
  .card, .chart-card, table.data, .auction, .gloss .g{-webkit-print-color-adjust:exact; print-color-adjust:exact}
  .sec-head, .sec-lede, h3{break-after:avoid} thead{display:table-header-group}
  footer{break-inside:avoid} footer p{font-size:9.5px}
  .card, .chart-card{padding:10px 12px}
  .tile .val{font-size:22px} .sec-head h2{font-size:17px} .bullets{font-size:11.5px}
  table.data{font-size:9.5px} table.data td, table.data th{padding:3px 6px 3px 0}
  table.data td.meaning{font-size:9.5px}
  #equities table.data{font-size:8.3px} #equities table.data td, #equities table.data th{padding:2px 4px 2px 0}
  .twrap{overflow:visible}
  .grid{gap:8px} .two{gap:8px} #trend .two{grid-template-columns:1fr} .chart-foot{display:none}
  .grid.c2w{grid-template-columns:1.15fr 1fr} .two{grid-template-columns:1fr 1fr} .grid.c4{grid-template-columns:repeat(4,1fr)}
  #bonds .grid.c2w{grid-template-columns:1fr} .pair{grid-template-columns:1fr 1fr} .tape-pause{display:none}
  .card{break-inside:auto} .card.tile, .chart-card, .auction, tr, .ts{break-inside:avoid}
  .tile .val{font-size:19px} .tile .val .delta{font-size:10px}
  section.pb, #trend{break-before:page}
  footer{background:#fff; color:var(--ink2); margin-top:14px} footer h4, .foot-bar b{color:var(--ink)} footer a{color:var(--ink2)}
  .foot-in{padding:10px 0; grid-template-columns:1fr 1fr; gap:14px; font-size:10px} .foot-bar{padding:8px 0; font-size:10px}
  .plain{font-size:10.5px} .sec-lede{font-size:11px}
  .gloss{columns:3} .gloss dt{font-size:10.5px} .gloss dd{font-size:9.5px}
  a{text-decoration:none; color:inherit}
}
"""

WORDMARK = """<span class="the">The</span><span class="tick">ticker<span class="tris" aria-hidden="true">
<svg width="22" height="20" viewBox="0 0 26 24"><path d="M13 2 L24 22 L2 22 Z" fill="none" stroke="#1fbf75" stroke-width="4" stroke-linejoin="round"/></svg>
<svg width="22" height="20" viewBox="0 0 26 24" style="align-self:flex-end"><path d="M13 22 L2 2 L24 2 Z" fill="none" stroke="#e8453c" stroke-width="4" stroke-linejoin="round"/></svg></span></span>"""

GLOSSARY = [
    ("Counter", "One listed company's shares, named by its ticker code (CRDB, NMB, VODA...)."),
    ("Turnover", "The total value of shares bought and sold, in Tanzanian shillings. The best single measure of how busy the market was."),
    ("Volume", "The number of shares that changed hands."),
    ("Deal", "One completed transaction between a buyer and a seller."),
    ("Market capitalisation", "Shares in issue multiplied by the share price: what the whole company (or market) is worth at today's prices."),
    ("DSEI", "The All Share Index — tracks the prices of every company listed on the DSE, including the cross-listed Kenyan companies."),
    ("TSI", "The Tanzania Share Index — the same idea, Tanzanian companies only."),
    ("Index points", "An index is a weighted average of prices scaled to a starting value; only the percentage change day to day is meaningful."),
    ("Cross-listed", "A company whose main listing is on the Nairobi Securities Exchange (marked ‡ in the table). Its DSE price follows its Nairobi close and it rarely trades here."),
    ("Bids and offers", "Orders waiting in the book at the close: bids want to buy, offers want to sell. Many more bids than offers suggests demand is waiting for sellers."),
    ("Block trade", "A large pre-arranged deal between two parties, crossed on the exchange's block board rather than in normal trading."),
    ("Foreign participation", "The share of buying and selling done by non-resident investors. A net inflow means foreigners bought more than they sold."),
    ("ETF", "Exchange-traded fund — a basket of shares that trades on the exchange as one share."),
    ("Treasury bond", "Government borrowing for 2 to 25 years that pays a fixed coupon twice a year. Sold at Bank of Tanzania auctions, then traded on the DSE."),
    ("Treasury bill", "Government borrowing for 35 to 364 days, sold below face value and repaid at face value; the discount is the interest."),
    ("Coupon", "The fixed annual interest a bond pays on its face value, set when the bond is first issued."),
    ("Price per 100", "Bond prices are quoted per 100 of face value. Exchange prices include interest built up since the last coupon; the clean price strips it out, and a clean price above 100 is a premium, below 100 a discount."),
    ("Yield (to maturity)", "The annual return a buyer locks in at today's price if the bond is held to the end. Prices and yields move in opposite directions."),
    ("Weighted average price / yield", "The average of today's trades (or auction allocations), weighted by the amount of each — so one big deal counts for more than ten small ones."),
    ("Bid-to-cover", "Total bids divided by the amount offered at an auction. 2.6 times means investors wanted 2.6 shillings for every shilling on sale."),
    ("Unit trust / CIS", "A collective investment scheme that pools investors' money into one professionally managed fund; you own units of the fund."),
    ("NAV per unit", "Net asset value per unit — the fund's assets minus liabilities, divided by the units in issue. Managers set their buying and selling prices from it, sometimes with a small charge, so the price you pay may differ slightly."),
    ("YTD", "Year to date: the change since the last valuation of the previous year."),
    ("Annualised", "A year-to-date return stretched to a full 365 days so funds can be compared regardless of the date."),
]


def _cls(v, dp=2):
    """Colour class from the value as it will be printed, so '0.0%' is never red or green."""
    if v is None:
        return "fl"
    r = round(v, dp)
    return "up" if r > 0 else "dn" if r < 0 else "fl"


def _tri(v, dp=2):
    c = _cls(v, dp)
    word = {"up": "up", "dn": "down", "fl": "unchanged"}[c]
    return f'<span class="tri {c}"><span class="sr-only">{word}</span></span>'


def _delta(v, dp=2, suffix="%"):
    if v is None:
        return '<span class="delta fl"><span class="tri fl"></span>n/a</span>'
    c = _cls(v, dp)
    txt = fpct(v, dp) if suffix == "%" else f"{v:+,.{dp}f}{suffix}"
    return f'<span class="delta {c}">{_tri(v, dp)}{txt}</span>'


def _chg_td(v, dp=1):
    return f'<td class="chg {_cls(v, dp)}">{fpct(v, dp)}</td>'


_SEC_COUNTER = {"n": 0}


def sec(id_, kicker, title, lede, extra_cls=""):
    _SEC_COUNTER["n"] += 1
    return (f'<section id="{id_}" class="{extra_cls}"><div class="sec-head"><span class="kicker"><b>{_SEC_COUNTER["n"]:02d}</b>{_e(kicker)}</span>'
            f'<h2>{_e(title)}</h2></div>' + (f'<p class="sec-lede">{lede}</p>' if lede else ""))


def tile(label, value, unit="", delta_html="", sub="", plain="", spark=""):
    return (f'<div class="card tile"><div class="lbl">{_e(label)}</div><div class="val">{value}'
            + (f'<span class="unit">{_e(unit)}</span>' if unit else "") + delta_html + "</div>"
            + (f'<div class="sub">{sub}</div>' if sub else "") + (f'<div class="spark">{spark}</div>' if spark else "")
            + (f'<div class="plain">{plain}</div>' if plain else "") + "</div>")


def chart_card(title, note, svg, legend_html="", host_cls=""):
    return (f'<div class="chart-card"><div class="chart-head"><div><h3>{_e(title)}</h3>'
            + (f'<p class="note">{_e(note)}</p>' if note else "") + "</div>" + legend_html + "</div>"
            + f'<div class="chart-host {host_cls}">{svg}</div></div>')


# ──────────────────────────────────────────────────────────────────────
def _as_date(x):
    return parse_iso(x) if isinstance(x, str) else x


def render(ds: dict, archive: list[dict], rel: str = "", pdf_name: str | None = None) -> str:
    # the dataset may come straight from the builder (date objects) or from data/*.json (strings)
    for key in ("bond", "tbill"):
        a_ = (ds.get("auctions") or {}).get(key)
        if a_ and a_.get("date"):
            a_["date"] = _as_date(a_["date"])
    for f_ in ds.get("cis") or []:
        if f_.get("date"):
            f_["date"] = _as_date(f_["date"])
    _SEC_COUNTER["n"] = 0
    d = parse_iso(ds["date"])
    pd_ = parse_iso(ds["prev_date"])
    t, p = ds["totals"], ds.get("prev_totals") or {}
    issue_no = max(1, sum(1 for x in archive if x.get("date", "") <= ds["date"]))
    idx = {i["code"]: i for i in ds["indices"]}
    pe = (ds.get("participation") or {}).get("equity") or {}
    hist = ds.get("history") or []
    title = f"DSE Daily Market Report · {short_date(d)} · The Ticker"

    # ── tape ───────────────────────────────────────────────────────
    tape = []
    for code in ("DSEI", "TSI"):
        if code in idx:
            tape.append((code, fnum(idx[code]["close"], 2), idx[code]["change_pct"]))
    tape.append(("TURNOVER", tzs_compact(t["turnover"]), (t["turnover"] / p["turnover"] - 1) * 100 if p.get("turnover") else None))
    if t.get("deals") is not None:
        tape.append(("DEALS", fnum(t["deals"]), None))
    net = pe.get("net_foreign_mln")
    if net is not None:
        tape.append(("FOREIGN NET", ("+" if net >= 0 else "−") + tzs_compact(abs(net) * 1e6).replace("TZS ", ""), net))
    if ds["bonds"]["available"]:
        tape.append(("BONDS TRADED", tzs_compact(ds["bonds"]["total_turnover_mln"] * 1e6).replace("TZS ", ""), None))
    for g in ds["gainers"][:2]:
        tape.append((g["code"], f"{fnum(g['close'])} {fpct(g['change_pct'])}", g["change_pct"]))
    for l in ds["losers"][:2]:
        tape.append((l["code"], f"{fnum(l['close'])} {fpct(l['change_pct'])}", l["change_pct"]))
    a = ds["auctions"].get("bond")
    if a and a.get("way"):
        tape.append((f"{int(a['term'])}Y AUCTION", f"{fnum(a['way'],2)}%", None))
    tape_html = "".join(f'<span class="tape-item"{" aria-hidden=true" if k else ""}><span class="tl">{_e(l)}</span><span class="tv">{_e(v)}</span>{_tri(c)}</span>'
                        for k in (0, 1) for l, v, c in tape)

    # ── summary section ────────────────────────────────────────────
    bullets = N.summary_bullets(ds)
    sp_turn = charts.sparkline([h.get("turnover") for h in hist]) if len(hist) > 2 else ""
    sp_dsei = charts.sparkline([h.get("dsei") for h in hist]) if len(hist) > 2 else ""
    sp_tsi = charts.sparkline([h.get("tsi") for h in hist]) if len(hist) > 2 else ""
    turn_chg = (t["turnover"] / p["turnover"] - 1) * 100 if (p.get("turnover") and t.get("turnover") is not None) else None
    flow = N.flow_state(pe)
    first_hist = next((h for h in hist if h.get("date")), None)
    span_txt = f"since {tiny_date(parse_iso(first_hist['date']))}" if first_hist and len(hist) > 2 else ""
    kpis = "".join([
        tile("Equity turnover", f"{t['turnover']/1e9:,.2f}", "TZS bn", _delta(turn_chg, 1), f"{fnum(t['deals'])} deals · {fnum(t['volume'])} shares",
             f"Previous session: {tzs_compact(p['turnover'])}.", sp_turn),
        tile("All Share Index (DSEI)", fnum(idx["DSEI"]["close"], 2) if "DSEI" in idx else "—", "", _delta(idx["DSEI"]["change_pct"]) if "DSEI" in idx else "",
             f"{span_txt} · 30-session trend" if span_txt else "", "Every listed company, weighted by size.", sp_dsei),
        tile("Tanzania Share Index (TSI)", fnum(idx["TSI"]["close"], 2) if "TSI" in idx else "—", "", _delta(idx["TSI"]["change_pct"]) if "TSI" in idx else "",
             f"{span_txt} · 30-session trend" if span_txt else "", "Tanzanian companies only.", sp_tsi),
        tile("Foreign investors", (("+" if net >= 0 else "−") + f"{abs(net):,.1f}") if net is not None else "—", "TZS m net" if net is not None else "",
             (f'<span class="delta {"up" if flow == "in" else "dn" if flow == "out" else "fl"}">'
              f'{"net inflow" if flow == "in" else "net outflow" if flow == "out" else "balanced"}</span>') if flow else "",
             (f"{fpct(pe.get('pct_buy_foreign'),0,False)} of buying · {fpct(pe.get('pct_sell_foreign'),0,False)} of selling" if pe else "awaiting DSE report"),
             "Bought minus sold by non-residents." if pe else "Published with the exchange's own daily report."),
    ])
    summary_html = sec("summary", "The session in one minute", f"{human_date(d)}",
                       f"What mattered on the Dar es Salaam Stock Exchange in this session, in plain language. Figures compare with the previous session, {human_date(pd_)}.")
    summary_html += f'<div class="card"><ul class="bullets">{"".join(f"<li>{b}</li>" for b in bullets)}</ul></div>'
    summary_html += f'<div class="grid c4" style="margin-top:14px">{kpis}</div></section>'

    # ── trend section (last 30 sessions) ───────────────────────────
    trend_html = ""
    if len(hist) >= 3:
        xl = [h["date"] for h in hist]
        xf = lambda iso_: tiny_date(parse_iso(iso_))
        idx_chart = charts.line_chart(xl, [{"name": "DSEI (all shares)", "color": "var(--s1)", "values": [h.get("dsei") for h in hist]},
                                           {"name": "TSI (Tanzanian)", "color": "var(--s2)", "values": [h.get("tsi") for h in hist]}],
                                      unit="", dp=1, aria="DSEI and TSI over the last 30 sessions, rebased to 100", x_fmt=xf, rebase=True)
        turn_chart = charts.column_series(xl, [h.get("turnover") for h in hist], unit=" bn", dp=2, scale=1e9,
                                          aria="Daily equity turnover over the last 30 sessions, TZS billion", x_fmt=xf,
                                          value_fmt=lambda v: f"TZS {v:,.2f} bn")
        trend_html = sec("trend", "The last 30 sessions", "Where the market has been",
                         N.trend_text(ds))
        trend_html += ('<div class="two">'
                       + chart_card("Share-price indices, rebased to 100", f"Both indices set to 100 on {xf(xl[0])}, so the lines show percentage change since then. Hover or use the arrow keys for exact values.",
                                    idx_chart, charts.legend([("DSEI (all shares)", "var(--s1)"), ("TSI (Tanzanian)", "var(--s2)")]), host_cls="scroll")
                       + chart_card("Daily equity turnover", "TZS billion per session; the latest session in dark blue, the dashed line is the 30-session average.", turn_chart, host_cls="scroll")
                       + '</div></section>')

    # ── key indicators table ───────────────────────────────────────
    mean = N.indicator_meanings(ds)
    mc = ds["market_caps"]
    rows = [
        ("Total turnover (TZS million)", p.get("turnover") / 1e6 if p.get("turnover") is not None else None, (t.get("turnover") or 0) / 1e6, 1, mean["turnover"]),
        ("Volume of shares traded", p.get("volume"), t.get("volume"), 0, mean["volume"]),
        ("Number of deals", p.get("deals"), t.get("deals"), 0, mean["deals"]),
        ("Total market capitalisation (TZS billion)", mc["total"]["prev"], mc["total"]["today"], 1, mean["total_cap"]),
        ("Domestic market capitalisation (TZS billion)", mc["domestic"]["prev"], mc["domestic"]["today"], 1, mean["domestic_cap"]),
        ("ETF market capitalisation (TZS billion)", mc["etf"]["prev"], mc["etf"]["today"], 1, mean["etf_cap"]),
    ]
    for i in ds["indices"]:
        rows.append((i["name"], i["prev_close"], i["close"], 2, mean.get(i["code"], "")))
    trs = []
    for name, prev, today, dp, meaning in rows:
        chg = ((today / prev - 1) * 100) if (today is not None and prev) else None
        trs.append(f"<tr><td class='l'>{_e(name)}</td><td>{fnum(prev, dp)}</td><td><b>{fnum(today, dp)}</b></td>{_chg_td(chg, 2)}<td class='meaning'>{meaning}</td></tr>")
    ind_html = sec("indicators", "Key market indicators", "The scoreboard",
                   "Each row shows the previous session, today, and the change. The right-hand column says what the number means.")
    ind_html += (f'<div class="card"><div class="twrap"><table class="data"><thead><tr><th class="l">Indicator</th><th>{tiny_date(pd_)}</th>'
                 f'<th>{tiny_date(d)}</th><th>Change</th><th class="l">What it means</th></tr></thead><tbody>{"".join(trs)}</tbody></table></div></div>')
    if ds.get("fx"):
        fxs = " · ".join(f"{k} {fnum(v['today'],2)}" for k, v in ds["fx"].items() if v.get("today"))
        ind_html += f'<p class="sec-lede" style="margin-top:12px;font-size:13px">Bank of Tanzania mean exchange rates on the day: {fxs}.</p>'
    ind_html += "</section>"

    # ── movers + gainers/losers ────────────────────────────────────
    maxp = max([m["share_pct"] for m in ds["movers"]] or [1]) or 1
    share_html = '<div class="sharebars">' + "".join(
        f'<span class="lb">{_e(m["code"])}</span><span class="bar {"other" if m["code"] == "Others" else "top" if i == 0 else ""}" style="width:{max(1.5, m["share_pct"] / maxp * 100):.1f}%"></span>'
        f'<span class="vl">{fnum(m["share_pct"],1)}% · {tzs_compact(m["turnover"]).replace("TZS ", "")}</span>'
        for i, m in enumerate(ds["movers"])) + "</div>" if ds["movers"] else '<div class="empty">No shares were traded</div>'
    mv_html = sec("movers", "Where the money went", "Top movers, gainers and losers",
                  "Movers are the counters that attracted the most money today. Gainers and losers are the biggest price changes, close versus previous close.")
    gl_rows = "".join(f"<tr><td>{_e(x['code'])}</td><td>{fnum(x['prev_close'])}</td><td>{fnum(x['close'])}</td>{_chg_td(x['change_pct'])}<td>{fnum(x['deals'])}</td></tr>"
                      for x in ds["gainers"] + ds["losers"])
    if not gl_rows:
        gl_rows = "<tr><td colspan='5' class='l'>No price changed today.</td></tr>"
    mv_html += ('<div class="grid c2w">'
                + chart_card("Share of the session's equity turnover", f"Top counters by value traded; total {tzs_compact(t['turnover'])}.", share_html)
                + f'<div class="card"><h3 style="margin:0 0 8px;font-size:15px">Top gainers and losers</h3><div class="twrap"><table class="data"><thead><tr><th class="l">Counter</th><th>Prev close</th><th>Close</th><th>Change</th><th>Deals</th></tr></thead><tbody>{gl_rows}</tbody></table></div>'
                + f'<div class="plain">{N.gainers_losers_text(ds)}</div></div></div>')
    mv_html += f'<p class="sec-lede" style="margin-top:14px">{N.movers_text(ds)}</p></section>'

    # ── participation ──────────────────────────────────────────────
    part_html = sec("participation", "Investor participation", "Foreign versus local investors",
                    "Who was buying and who was selling. Percentages are shares of the day's turnover; the totals come from the exchange's own daily report.")
    pt = (ds.get("participation") or {}).get("etf") or {}
    if pe:
        g_eq = [("Buying", [pe.get("pct_buy_local"), pe.get("pct_buy_foreign")]), ("Selling", [pe.get("pct_sell_local"), pe.get("pct_sell_foreign")])]
        lg = charts.legend([("Local", "var(--s1)"), ("Foreign", "var(--s2)")])
        c1 = chart_card("Equities", (f"Net foreign flow {'+' if net >= 0 else '−'}TZS {fnum(abs(net),1)} million" if net is not None else "Net foreign flow not published"),
                        charts.grouped_columns(g_eq, ["Local", "Foreign"], ["var(--s1)", "var(--s2)"], aria="Equity participation"), lg)
        if pt:
            g_etf = [("Buying", [pt.get("pct_buy_local"), pt.get("pct_buy_foreign")]), ("Selling", [pt.get("pct_sell_local"), pt.get("pct_sell_foreign")])]
            c2 = chart_card("ETFs", f"Turnover TZS {fnum(pt['total_turnover_mln'],1)} million · net foreign {'+' if (pt.get('net_foreign_mln') or 0)>=0 else '−'}TZS {fnum(abs(pt.get('net_foreign_mln') or 0),2)} million",
                            charts.grouped_columns(g_etf, ["Local", "Foreign"], ["var(--s1)", "var(--s2)"], aria="ETF participation"), lg)
        else:
            c2 = ""
        part_html += f'<div class="two">{c1}{c2}</div>'
    part_html += f'<p class="sec-lede" style="margin-top:14px">{N.participation_text(ds)}</p></section>'

    # ── bonds ──────────────────────────────────────────────────────
    bd = ds["bonds"]
    bond_html = sec("bonds", "Bonds", "Government bonds on the exchange",
                    "Treasury bonds change hands on the DSE after they are first sold at Bank of Tanzania auctions. Price is per 100 of face value; yield is the annual return locked in at that price.")
    def _pv(v, dp=2, suffix=""):
        return (fnum(v, dp) + suffix) if v else "—"
    bt_rows = "".join(f"<tr><td>{b['term']}-year</td><td>{fnum(b['deals'])}</td><td>{fnum(b['turnover_mln'],1)}</td><td>{_pv(b['wa_price'])}</td><td>{_pv(b.get('wa_clean'))}</td><td>{_pv(b['wa_yield'],2,'%')}</td></tr>"
                      for b in bd["by_term"])
    bt_rows += (f"<tr class='total'><td>Total</td><td>{fnum(bd['total_deals'])}</td><td>{fnum(bd['total_turnover_mln'],1)}</td><td>{_pv(bd['wa_price'])}</td>"
                f"<td>{_pv(bd.get('wa_clean'))}</td><td>{_pv(bd['wa_yield'],2,'%')}</td></tr>")
    bond_html += ('<div class="grid c2w">'
                  f'<div class="card"><h3 style="margin:0 0 8px;font-size:15px">Daily bonds performance by term</h3><div class="twrap"><table class="data"><thead><tr><th class="l">Term</th><th>Deals</th><th>Turnover (TZS m)</th><th>W.A. price</th><th>W.A. clean price</th><th>W.A. yield</th></tr></thead><tbody>{bt_rows}</tbody></table></div>'
                  f'<div class="plain">{N.bonds_text(ds)}</div></div>'
                  '<div class="pair">'
                  + chart_card("Weighted average price by term", "Per 100 of face value, including accrued interest; only terms that traded.", charts.tenor_columns(bd["by_term"][:7], "wa_price", "", 1, aria="Weighted average bond price by term"))
                  + chart_card("Weighted average yield by term", "Annual return to maturity at the prices paid.", charts.tenor_columns(bd["by_term"][:7], "wa_yield", "%", 2, aria="Weighted average bond yield by term"))
                  + '</div></div>')
    all_tr = (bd.get("trades") or []) + (bd.get("other_bonds") or [])
    if all_tr:
        tr_rows = "".join(f"<tr><td>{_e(str(x['bond_no']))}</td><td>{fnum(x['term'])}</td><td>{fnum(x['coupon'],2)}%</td><td>{_e(str(x['maturity_date']))}</td><td>{fnum(x['deals'])}</td><td>{fnum((x['amount_bn'] or 0)*1000,1)}</td><td>{fnum(x['price'],4)}</td><td>{fnum(x['yield'],4)}%</td><td>{fnum(x['clean_price'],4)}</td></tr>"
                          for x in all_tr)
        bond_html += (f'<details class="screen-only" style="margin-top:12px"><summary style="cursor:pointer;font-size:13px;color:var(--ink2);font-weight:600">Every bond trade in the session ({len(all_tr)})</summary>'
                      f'<div class="card" style="margin-top:8px"><div class="twrap"><table class="data"><thead><tr><th class="l">Bond</th><th>Term</th><th>Coupon</th><th>Maturity</th><th>Deals</th><th>Face value (TZS m)</th><th>Price</th><th>Yield</th><th>Clean price</th></tr></thead><tbody>{tr_rows}</tbody></table></div></div></details>')
    # auctions
    a, tb = ds["auctions"].get("bond"), ds["auctions"].get("tbill")
    bond_html += '<h3 style="margin:26px 0 6px;font-size:17px">Latest Bank of Tanzania auctions</h3>'
    bond_html += '<p class="sec-lede">The primary market: where the Government borrows and the yield for each maturity is set. These are the most recent results, whatever day they were held.</p>'
    if a:
        auc_tiles = "".join(f'<div class="ts"><div class="k">{_e(k)}</div><div class="v">{_e(v)}</div></div>' for k, v in [
            ("Bond", f"{fnum(a['coupon'],2)}% {int(a['term'])}-year · No. {a['auction_no']}"), ("Auction date", short_date(a["date"]) if a.get("date") else "—"),
            ("On offer", f"TZS {fnum(a['offered_mln']/1000,1)} bn"), ("Bids received", f"TZS {fnum(a['tendered_mln']/1000,1)} bn ({a['bid_to_cover']:.1f}×)" if a.get("bid_to_cover") else f"TZS {fnum(a['tendered_mln']/1000,1)} bn"),
            ("Allotted", f"TZS {fnum(a['successful_mln']/1000,1)} bn"), ("Weighted average price", f"{fnum(a['wap'],4)} per 100"),
            ("Weighted average yield", f"{fnum(a['way'],4)}%"), ("Minimum successful price", f"{fnum(a['min_successful_price'],4)}"),
        ])
        bond_html += f'<div class="card"><h3 style="margin:0;font-size:15px">Treasury bond auction</h3><div class="auction">{auc_tiles}</div><div class="plain">{N.auction_bond_text(a)}</div></div>'
    else:
        bond_html += f'<div class="card"><div class="plain">{N.auction_bond_text(None)}</div></div>'
    if tb:
        hdr = "".join(f"<th>{_e(x)}</th>" for x in tb["tenors"])

        def row(label, vals, fmt):
            return f"<tr><td class='l'>{_e(label)}</td>" + "".join(f"<td>{fmt(v) if v is not None else '—'}</td>" for v in vals) + "</tr>"
        tb_rows = "".join([
            row("Maturity date", tb["maturity"], lambda v: _e(str(v))),
            row("Bids received / successful", list(zip(tb["bids"], tb["successful_bids"])), lambda v: f"{fnum(v[0])} / {fnum(v[1])}"),
            row("Weighted average price (per 100)", tb["wap"], lambda v: fnum(v, 4)),
            row("Weighted average yield", tb["way"], lambda v: f"<b>{fnum(v,4)}%</b>"),
            row("Amount offered (TZS m)", tb["offered_mln"], lambda v: fnum(v)),
            row("Amount tendered (TZS m)", tb["tendered_mln"], lambda v: fnum(v)),
            row("Allotted (TZS m)", tb["successful_mln"], lambda v: fnum(v)),
            row("Bid-to-cover", tb["bid_to_cover"], lambda v: f"{v:.2f}×"),
        ])
        bond_html += (f'<div class="card" style="margin-top:14px"><h3 style="margin:0 0 8px;font-size:15px">Treasury bill auction No. {_e(tb["auction_no"])}'
                      + (f' · {short_date(tb["date"])}' if tb.get("date") else "") + f'</h3><div class="twrap"><table class="data"><thead><tr><th class="l"><span class="sr-only">Measure</span></th>{hdr}</tr></thead><tbody>{tb_rows}</tbody></table></div>'
                      f'<div class="plain">{N.auction_tbill_text(tb)}</div></div>')
    bond_html += "</section>"

    # ── funds ──────────────────────────────────────────────────────
    cis_rows = "".join(
        f"<tr><td class='l'>{_e(f['fund'])}<span style='display:block;font-size:10.5px;color:var(--muted);font-weight:400'>{_e(f['manager'])}</span></td><td>{tiny_date(f['date']) if f.get('date') else '—'}</td>"
        f"<td>{fnum((f['nav_total'] or 0)/1e6)}</td><td>{fnum(f['nav_per_unit'],4)}</td>{_chg_td(f['daily_change_pct'],2)}{_chg_td(f['ytd_pct'],1)}{_chg_td(f['annualised_pct'],1)}</tr>"
        for f in (ds.get("cis") or []))
    cis_html = sec("funds", "Unit trusts", "Collective investment schemes",
                   "The latest published unit prices from Tanzanian fund managers. Each manager publishes on its own schedule, so dates differ.")
    cis_html += (f'<div class="card"><div class="twrap"><table class="data"><thead><tr><th class="l">Fund</th><th>Valued</th><th>Fund size (TZS m)</th><th>NAV per unit</th><th>Daily</th><th>YTD (NAV)</th><th>Annualised</th></tr></thead>'
                 f'<tbody>{cis_rows or "<tr><td colspan=7 class=l>No fund prices collected.</td></tr>"}</tbody></table></div><div class="plain">{N.cis_text(ds)}</div></div></section>')

    # ── all equities + ETFs ────────────────────────────────────────
    max_turn = max([e["turnover"] or 0 for e in ds["equities"]] or [1]) or 1
    eq_rows = "".join(
        f"<tr><td>{_e(e['code'])}{'‡' if e['cross_listed'] else ''}</td><td>{fnum(e['prev_close'])}</td><td>{fnum(e['close'])}</td>{_chg_td(e['change_pct'])}"
        f"<td>{fnum(e['year_start'])}</td>{_chg_td(e['ytd_pct'])}<td>{fnum(e['turnover'])}"
        + (f"<span class='dbar' style='width:{(e['turnover'] or 0) / max_turn * 100:.1f}%'></span>" if (e['turnover'] or 0) / max_turn >= 0.005 else "")
        + f"</td><td>{fnum(e['deals'])}</td><td>{fnum(e['bids'])}</td><td>{fnum(e['offers'])}</td><td>{fnum(e['volume'])}</td><td>{fnum(e['market_cap_bn'],2)}</td></tr>"
        for e in ds["equities"])
    eq_rows += (f"<tr class='total'><td>Total</td><td></td><td></td><td></td><td></td><td></td><td>{fnum(t['turnover'])}</td><td>{fnum(t['deals'])}</td>"
                f"<td>{fnum(t['bids'])}</td><td>{fnum(t['offers'])}</td><td>{fnum(t['volume'])}</td><td>{fnum(t['market_cap_bn'],2)}</td></tr>")
    eq_html = sec("equities", "All counters", "DSE daily equities performance", N.equities_table_note(ds), "pb")
    eq_html += (f'<div class="card"><div class="twrap"><table class="data"><thead><tr><th class="l">Counter</th><th>Prev close</th><th>Close</th><th>Change</th><th>Year start</th><th>YTD</th>'
                f'<th>Turnover (TZS)</th><th>Deals</th><th>Bids</th><th>Offers</th><th>Volume</th><th>Mkt cap (bn)</th></tr></thead><tbody>{eq_rows}</tbody></table></div></div>')
    if ds.get("etfs"):
        etf_rows = "".join(
            f"<tr><td>{_e(x['code'])}</td><td>{fnum(x.get('prev_close'))}</td><td>{fnum(x.get('close'))}</td>{_chg_td(x.get('change_pct'))}<td>{fnum(x.get('high'))}</td><td>{fnum(x.get('low'))}</td>"
            f"<td>{fnum(x.get('turnover'))}</td><td>{fnum(x.get('deals'))}</td><td>{fnum(x.get('volume'))}</td><td>{fnum(x.get('bids'))}</td><td>{fnum(x.get('offers'))}</td><td>{fnum(x.get('market_cap_bn'),2)}</td></tr>"
            for x in ds["etfs"])
        eq_html += (f'<div class="card" style="margin-top:14px"><h3 style="margin:0 0 8px;font-size:15px">ETF daily performance</h3><div class="twrap"><table class="data"><thead><tr><th class="l">ETF</th><th>Prev close</th><th>Close</th><th>Change</th><th>High</th><th>Low</th><th>Turnover (TZS)</th><th>Deals</th><th>Volume</th><th>Bids</th><th>Offers</th><th>Mkt cap (bn)</th></tr></thead><tbody>{etf_rows}</tbody></table></div>'
                    f'<div class="plain">{N.etf_text(ds)}</div></div>')
    eq_html += "</section>"

    # ── glossary / sources / archive ───────────────────────────────
    gl = "".join(f'<div class="g"><dt>{_e(a)}</dt><dd>{_e(b)}</dd></div>' for a, b in GLOSSARY)
    gloss_html = sec("glossary", "Glossary", "The jargon, translated", "") + f'<dl class="gloss">{gl}</dl>'
    if ds.get("notes"):
        gloss_html += '<div class="notes"><b>Build notes.</b> ' + " ".join(_e(n) for n in ds["notes"]) + "</div>"
    gloss_html += ('<div class="disclaimer"><b>Important.</b> This report is generated automatically from public data published by the Dar es Salaam Stock Exchange, '
                   'the Bank of Tanzania and licensed fund managers. It is an educational summary, not investment advice and not an offer to buy or sell any security. '
                   'Figures can be revised by their publishers; confirm against the official source before acting. © The Ticker. May be shared unaltered with this notice.</div></section>')

    # archive listing (screen only)
    arch_items = "".join(f'<li><a href="{rel}archive/{x["date"]}.html">{short_date(parse_iso(x["date"]))}</a>'
                         + (f' · <a href="{rel}archive/{x["date"]}.pdf">PDF</a>' if x.get("pdf") else "") + "</li>" for x in archive[:12])
    sources = [("DSE market data and daily Market Report", "https://dse.co.tz/"),
               ("Bank of Tanzania Treasury bond auctions", "https://www.bot.go.tz/TBonds"),
               ("Bank of Tanzania Treasury bill auctions", "https://www.bot.go.tz/TBills")]
    for s_ in ds["sources"].get("cis") or []:
        sources.append((s_.split("//")[1].split("/")[0].replace("www.", ""), s_))
    if ds["sources"].get("dse_report_url"):
        sources.insert(1, (f"DSE Market Report, {short_date(d)}", ds["sources"]["dse_report_url"]))
    src_html = "".join(f'<li><a href="{_e(u)}" target="_blank" rel="noopener">{_e(n)}</a></li>' for n, u in sources)

    pdf_link = f'<a class="btn" href="{rel}archive/{pdf_name}">Download PDF &darr;</a>' if pdf_name else ""
    heroes = [("Equity turnover", f"TZS {t['turnover']/1e9:,.2f} bn" if t.get("turnover") else "—", _delta(turn_chg, 1) if turn_chg is not None else ""),
              ("All Share Index (DSEI)", fnum(idx["DSEI"]["close"], 2) if "DSEI" in idx else "—", _delta(idx["DSEI"]["change_pct"]) if "DSEI" in idx else ""),
              ("Tanzania Share Index (TSI)", fnum(idx["TSI"]["close"], 2) if "TSI" in idx else "—", _delta(idx["TSI"]["change_pct"]) if "TSI" in idx else ""),
              ("Foreign investors, net", (("+" if net >= 0 else "−") + f"TZS {abs(net):,.1f} m") if net is not None else "—",
               {"in": "net inflow", "out": "net outflow", "flat": "balanced"}.get(flow or "", "") if flow else "awaiting DSE report")]
    hero_html = "".join(f'<div class="hero"><div class="k">{_e(k)}</div><div class="v">{_e(v)}</div><div class="d">{dd}</div></div>' for k, v, dd in heroes)
    inside = ["The session in one minute", "Key market indicators", "Top movers, gainers and losers", "Foreign versus local investors",
              "Government bonds and the latest BOT auctions", "Unit trusts", "Every counter and ETF", "Glossary"]
    if trend_html:
        inside.insert(1, "The last 30 sessions")
    cover_html = (f'<section class="cover" aria-hidden="true"><div><div class="wordmark">{WORDMARK}</div>'
                  f'<div class="ctag">DAR ES SALAAM STOCK EXCHANGE · DAILY MARKET REPORT · ISSUE No. {issue_no}</div>'
                  f'<h1>DSE Daily Market Report</h1><p class="cdate">Market close, {human_date(d)}</p>'
                  f'<div class="heroes">{hero_html}</div>'
                  f'<div class="inside"><b>INSIDE THIS REPORT</b><ol>{"".join(f"<li>{_e(x)}</li>" for x in inside)}</ol></div></div>'
                  f'<div class="cfoot">Produced automatically from the Dar es Salaam Stock Exchange, Bank of Tanzania and fund-manager publications · '
                  f'built {_e(ds["generated_at"][:16].replace("T", " "))} EAT · {SITE}market-report/ · educational summary, not investment advice</div></section>')
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{_e(title)}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Plain-language daily report on the Dar es Salaam Stock Exchange: turnover, indices, movers, foreign participation, bonds, auctions and unit-trust prices for {short_date(d)}.">
<meta name="theme-color" content="#2c2015">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Poppins:wght@500;800&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>{CSS}</style></head>
<body>
{cover_html}
<header class="mast"><div class="mast-in">
  <a class="wordmark" href="{SITE}" aria-label="The Ticker">{WORDMARK}</a>
  <div class="mast-meta"><div class="tag">DAR ES SALAAM STOCK EXCHANGE · DAILY MARKET REPORT</div><span class="issue">ISSUE No. {issue_no}</span>
    <h1>Market close, {human_date(d)}</h1>
    <div class="asof">Built automatically <b>{_e(ds['generated_at'][:16].replace('T',' '))} EAT</b> from DSE, BOT and fund-manager publications</div>
    <div class="actions">{pdf_link}<a class="btn ghost" href="{rel}archive/">Past reports</a><a class="btn ghost" href="{SITE}">The Ticker home</a></div>
  </div></div>
  <div class="tape-wrap"><div class="tape" id="tape" role="marquee" aria-label="Key numbers"><div class="tape-track">{tape_html}</div></div>
  <button class="tape-pause" type="button" id="tape-pause" aria-pressed="false" onclick="var t=document.getElementById('tape');t.classList.toggle('paused');var on=t.classList.contains('paused');this.setAttribute('aria-pressed',on);this.textContent=on?'Play':'Pause'">Pause</button></div>
</header>
<nav class="nav" aria-label="Sections"><div class="nav-in">
  <a href="#summary">Summary</a>{'<a href="#trend">Trend</a>' if trend_html else ''}<a href="#indicators">Indicators</a><a href="#movers">Movers</a><a href="#participation">Foreign vs local</a>
  <a href="#bonds">Bonds &amp; auctions</a><a href="#funds">Unit trusts</a><a href="#equities">All counters</a><a href="#glossary">Glossary</a>
  <a class="tool" href="{rel}guide.html">Guide</a><a class="tool" href="{SITE}bond-calculator.html">Bond Calculator</a>
</div></nav>
<main>
{summary_html}
{trend_html}
{ind_html}
{mv_html}
{part_html}
{bond_html}
{cis_html}
{eq_html}
{gloss_html}
</main>
<footer><div class="foot-in">
  <div><h4>About this report</h4><p style="margin:0">The Ticker's DSE Daily Market Report is produced by an automated pipeline after each trading day: it reads the exchange's published prices and its daily Market Report, the Bank of Tanzania's auction results and fund managers' unit prices, then writes this page and its PDF. No numbers are typed by hand. The official sources for every figure are listed on the right.</p>
    <div class="foot-note">Report for {short_date(d)} · issue No. {issue_no} · generated {_e(ds['generated_at'][:16].replace('T',' '))} EAT · <a href="{rel}guide.html">how this report is made and how to run it</a></div>
    <div class="screen-only" style="margin-top:12px"><h4>Recent reports</h4><ul>{arch_items or '<li>—</li>'}</ul></div></div>
  <div><h4>Official sources</h4><ul>{src_html}</ul></div>
</div><div class="foot-bar">© {d.year} <b>The Ticker</b> — all rights reserved. Data: Dar es Salaam Stock Exchange, Bank of Tanzania and fund-manager publications.</div></footer>
<script>{TOOLTIP_JS}</script>
</body></html>"""
    html = html.replace("<th>", '<th scope="col">').replace('<th class="l">', '<th scope="col" class="l">')
    return html


TOOLTIP_JS = r"""
(function(){
  var MON=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  function dlabel(iso){var p=iso.split("-");return p.length===3?(+p[2])+" "+MON[+p[1]-1]+" "+p[0]:iso;}
  function fmt(v,dp){return v==null?"—":Number(v).toLocaleString("en-US",{minimumFractionDigits:dp,maximumFractionDigits:dp});}
  document.querySelectorAll("svg.tschart").forEach(function(svg){
    var cfg; try{cfg=JSON.parse(svg.getAttribute("data-chart"));}catch(e){return;}
    var host=svg.parentNode; var tip=document.createElement("div"); tip.className="tip"; host.appendChild(tip);
    var xh=svg.querySelector("line.xh"); var vb=svg.viewBox.baseVal; var n=cfg.x.length; var cur=-1;
    function show(i,clientX,clientY){
      if(i<0||i>=n){tip.style.opacity=0; if(xh)xh.setAttribute("opacity",0); return;}
      cur=i; var rows=cfg.series.map(function(s){var v=s.values[i]; return v==null?"":'<div class="trow"><span class="tkey" style="background:'+s.color+'"></span><span class="tval">'+fmt(v,cfg.dp)+(cfg.unit||"")+'</span><span class="tname">'+s.name+'</span></div>';}).join("");
      tip.innerHTML='<div class="tt">'+dlabel(cfg.x[i])+'</div>'+rows;
      var r=svg.getBoundingClientRect(); var sx=r.width/vb.width; var px=(cfg.plot[0]+cfg.plot[2]*(n===1?0.5:i/(n-1)))*sx;
      if(xh){xh.setAttribute("x1",cfg.plot[0]+cfg.plot[2]*(i/(n-1))); xh.setAttribute("x2",cfg.plot[0]+cfg.plot[2]*(i/(n-1))); xh.setAttribute("opacity",1);}
      var hr=host.getBoundingClientRect(); var left=(r.left-hr.left)+px+12; if(left+tip.offsetWidth>hr.width-4) left=(r.left-hr.left)+px-tip.offsetWidth-12;
      var top=clientY!=null?(clientY-hr.top-tip.offsetHeight-10):8; if(top<4) top=4;
      tip.style.left=Math.max(4,left)+"px"; tip.style.top=top+"px"; tip.style.opacity=1;
    }
    svg.addEventListener("mousemove",function(e){var r=svg.getBoundingClientRect(); var x=(e.clientX-r.left)/ (r.width/vb.width); var f=(x-cfg.plot[0])/cfg.plot[2]; var i=Math.round(f*(n-1)); if(i<0)i=0; if(i>n-1)i=n-1; show(i,e.clientX,e.clientY);});
    svg.addEventListener("mouseleave",function(){tip.style.opacity=0; if(xh)xh.setAttribute("opacity",0); cur=-1;});
    svg.addEventListener("keydown",function(e){var i=cur<0?n-1:cur; if(e.key==="ArrowLeft")i=Math.max(0,i-1); else if(e.key==="ArrowRight")i=Math.min(n-1,i+1); else if(e.key==="Home")i=0; else if(e.key==="End")i=n-1; else if(e.key==="Escape"){tip.style.opacity=0; if(xh)xh.setAttribute("opacity",0); cur=-1; return;} else return; e.preventDefault(); show(i,null,null);});
    svg.addEventListener("blur",function(){tip.style.opacity=0; if(xh)xh.setAttribute("opacity",0); cur=-1;});
  });
})();
"""


def render_archive(archive: list[dict]) -> str:
    items = "".join(
        f'<li class="card" style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:center;margin-bottom:10px">'
        f'<div><b>{human_date(parse_iso(x["date"]))}</b><div style="font-size:12.5px;color:var(--muted);font-family:var(--mono)">{_e(x.get("blurb",""))}</div></div>'
        f'<div style="display:flex;gap:8px"><a class="btn" style="background:var(--mast);color:var(--mast-ink)" href="{x["date"]}.html">Open</a>'
        + (f'<a class="btn" style="background:var(--card3);color:var(--ink)" href="{x["date"]}.pdf">PDF</a>' if x.get("pdf") else "") + "</div></li>"
        for x in archive)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>DSE Daily Market Report archive · The Ticker</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Poppins:wght@500;800&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>{CSS}</style></head><body>
<header class="mast"><div class="mast-in"><a class="wordmark" href="{SITE}" aria-label="The Ticker">{WORDMARK}</a>
<div class="mast-meta"><div class="tag">DAR ES SALAAM STOCK EXCHANGE · DAILY MARKET REPORT</div><h1>Report archive</h1>
<div class="actions"><a class="btn" href="../">Latest report</a><a class="btn ghost" href="{SITE}">The Ticker home</a></div></div></div></header>
<main><section id="archive"><div class="sec-head"><span class="kicker">Archive</span><h2>Every report, newest first</h2></div>
<ul style="list-style:none;padding:0;margin:14px 0 0">{items or '<li>No reports yet.</li>'}</ul></section></main>
<footer><div class="foot-bar">© <b>The Ticker</b> — all rights reserved.</div></footer></body></html>"""
