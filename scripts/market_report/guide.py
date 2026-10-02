"""The user guide, rendered in The Ticker's design to market-report/guide.html on every build."""
from __future__ import annotations

from html import escape as _e
from pathlib import Path

from .render import CSS, SITE, WORDMARK

SECTIONS = [
    ("what", "What this is", """
<p>The <b>DSE Daily Market Report</b> is a web page and PDF that The Ticker publishes after every trading day on the
Dar es Salaam Stock Exchange. It is produced entirely by a small program on your own computer: nobody types numbers,
and no cloud service or AI is involved on a normal day. The program reads public sources, works out the figures, writes the
explanations from fixed rules, renders the page and the PDF, saves a copy to your Desktop and (if you choose) publishes it
to the live site.</p>
<div class="grid c3">
  <div class="card"><div class="lbl">Reads</div><p class="plain">The DSE price feed and the exchange's own daily Market Report, the Bank of Tanzania's auction results, and the unit-price pages of UTT AMIS, Orbit (Inuka) and WHI (Faida).</p></div>
  <div class="card"><div class="lbl">Writes</div><p class="plain">One web page and one PDF per trading day, a machine-readable JSON dataset, an archive page, and a copy of each finished report in <b>Desktop › The Ticker Market Reports</b>.</p></div>
  <div class="card"><div class="lbl">Publishes (optional, off by default)</div><p class="plain">Nothing leaves your computer unless you switch publishing on. Later, with <code>REPORT_PUSH=1</code> and the three <code>market-report/…</code> lines removed from <code>.gitignore</code>, each run also commits and pushes, and GitHub Pages shows the report at <a href="{site}market-report/">{site}market-report/</a>.</p></div>
</div>"""),
    ("setup", "Set-up (once, about ten minutes)", """
<ol class="steps">
  <li><b>Install Python and Git.</b> Python 3.11 or newer from <a href="https://www.python.org/downloads/">python.org</a> (on Windows tick <i>Add python.exe to PATH</i>) and Git from <a href="https://git-scm.com/downloads">git-scm.com</a>. GitHub Desktop is a comfortable way to sign in so that <code>git push</code> works.</li>
  <li><b>Get the repository.</b> <code>git clone https://github.com/thetickertz/The-Ticker.git</code>, then open a terminal in the <code>The-Ticker</code> folder.</li>
  <li><b>Settings.</b> Copy <code>scripts/.env.example</code> to <code>scripts/.env</code>. The defaults build on this computer only and save every report to <b>Desktop › The Ticker Market Reports</b>; <code>REPORT_EXPORT_DIR</code> moves that folder. Fill in the SMTP lines only if you want the PDF e-mailed; set <code>REPORT_PUSH=1</code> only when you want to publish to the public site.</li>
  <li><b>First run.</b> Double-click <code>Ticker-Report.bat</code> (Windows) or <code>Ticker-Report.command</code> (macOS) in the repository folder and choose <i>1</i>, or in a terminal run
    <pre>Windows   powershell -ExecutionPolicy Bypass -File scripts\\run_daily.ps1
macOS/Linux   scripts/run_daily.sh</pre>
    The first run creates a private Python environment and downloads Chromium for the PDF (two or three minutes). Every later run takes about a minute.</li>
  <li><b>Put it on a timer.</b> From the menu choose <i>5</i>, or run <code>scripts\\schedule_windows.ps1</code> (Windows Task Scheduler) or <code>scripts/schedule_unix.sh</code> (cron). The job runs on weekdays at 16:40, 18:40 and 20:40 East Africa Time and at 08:10 the next morning, converted to your computer's clock. The computer must be on, or allowed to wake, at those times; a missed slot is simply picked up by the next one.</li>
</ol>"""),
    ("daily", "What happens on a normal day", """
<ol class="steps">
  <li>The job asks the DSE for its last trading day. Before 16:00 EAT on a trading day it stops, so an unfinished session is never published.</li>
  <li>If that day is already built from the exchange's full Market Report, it stops: nothing to do.</li>
  <li>Otherwise it fetches everything, derives the figures, writes the explanations, renders the web page and the PDF into <code>market-report/archive/</code> and updates the archive listing.</li>
  <li>It copies the PDF and the web page to <b>Desktop › The Ticker Market Reports</b>, named <code>The Ticker - DSE Daily Market Report - 2026-10-01.pdf</code> and <code>.html</code>. This folder is the deliverable: open the PDF, print it, or forward it.</li>
  <li>With SMTP settings it e-mails the PDF; with <code>REPORT_PUSH=1</code> it also commits and pushes to the public site.</li>
</ol>
<p>If the exchange has not yet posted its Market Report when a run happens, the report is still built from the price feed (prices, indices, movers, auctions, funds) with a note that participation and bond details will follow. The Desktop copy is named <i>(preliminary)</i>; a later run, even days later, builds the complete edition and replaces it.</p>
<p>Logs: <code>~/.the-ticker/run.log</code> (Windows: <code>%USERPROFILE%\\.the-ticker\\run.log</code>).</p>"""),
    ("menu", "The menu launcher", """
<p><code>Ticker-Report.bat</code> / <code>Ticker-Report.command</code> open a small menu so nothing has to be typed:</p>
<table class="data"><thead><tr><th class="l">Choice</th><th class="l">What it does</th></tr></thead><tbody>
<tr><td>1</td><td class="l">Build or refresh the latest trading day (the normal daily run)</td></tr>
<tr><td>2</td><td class="l">Rebuild a specific date you type (for example after a source correction)</td></tr>
<tr><td>3</td><td class="l">Open the latest report in your browser</td></tr>
<tr><td>4</td><td class="l">Open the Desktop folder of reports</td></tr>
<tr><td>5</td><td class="l">Install or remove the schedule</td></tr>
<tr><td>6</td><td class="l">Open this guide</td></tr>
<tr><td>7</td><td class="l">Show the current settings and where to change them</td></tr>
</tbody></table>
<p>Command-line equivalents for scripts and automation:</p>
<pre>python -m scripts.market_report.build                    # last trading day, if not built
python -m scripts.market_report.build --date 2026-10-01 --force
python -m scripts.market_report.build --no-pdf           # faster, web page only
scripts/run_daily.sh --date 2026-10-01 --force           # same, plus commit/push/e-mail/export</pre>"""),
    ("numbers", "How the numbers are derived", """
<table class="data"><thead><tr><th class="l">Figure</th><th class="l">Source and rule</th></tr></thead><tbody>
<tr><td class="l">Turnover, volume, deals</td><td class="l">DSE price feed, reconciled with the total in the exchange's Market Report (the report wins if they differ).</td></tr>
<tr><td class="l">Market capitalisation</td><td class="l">Sum of shares in issue × close for every counter, including suspended counters that the feed omits (taken from the report). Domestic excludes the Kenyan cross-listed companies.</td></tr>
<tr><td class="l">Change</td><td class="l">Close versus previous close, as the exchange reports it. Breadth, gainers and losers count only counters that traded on the DSE; cross-listed counters repriced from Nairobi without a local deal are listed separately.</td></tr>
<tr><td class="l">Year start, YTD</td><td class="l">Last close of the previous year, adjusted for a share split only when the share count changed by an integer ratio and the price stepped by the same ratio on one day.</td></tr>
<tr><td class="l">Foreign participation</td><td class="l">The report's "Equities Market Turnover" table; net flow = foreign buying − foreign selling. "Balanced" means the difference is under 2% of turnover (and under TZS 25 million).</td></tr>
<tr><td class="l">Bonds by term</td><td class="l">Every Treasury bond trade in the report, grouped by term; prices and yields weighted by face value; infrastructure and corporate lines listed separately. Exchange prices include accrued interest; the clean price strips it out.</td></tr>
<tr><td class="l">Auctions</td><td class="l">Bank of Tanzania results as published; bid-to-cover = amount tendered ÷ amount offered. BOT auction prices are clean prices.</td></tr>
<tr><td class="l">Unit trusts</td><td class="l">Each manager's own NAV page. Daily = change since the previous valuation; YTD = unit-price change since the last valuation of the previous year; annualised = YTD × 365 ÷ days elapsed, shown only after 30 days.</td></tr>
</tbody></table>
<p>Every day's parsed dataset is saved as <code>market-report/data/&lt;date&gt;.json</code>, so any figure can be traced, and anything that degraded is listed under <i>Build notes</i> at the foot of the report.</p>"""),
    ("trouble", "When something goes wrong", """
<table class="data"><thead><tr><th class="l">Symptom</th><th class="l">What it means and what to do</th></tr></thead><tbody>
<tr><td class="l">"python is not recognized" / "python3: command not found"</td><td class="l">Python is not installed or not on the PATH. Reinstall from python.org with <i>Add python.exe to PATH</i> ticked, then open a new terminal.</td></tr>
<tr><td class="l">"could not push" / authentication failed</td><td class="l">Git cannot sign in to GitHub. Sign in with GitHub Desktop or run <code>gh auth login</code>, then run the job again; the report is already built locally and will be pushed on the next run.</td></tr>
<tr><td class="l">"DSE has no equity data dated … yet" / "session may still be open"</td><td class="l">Normal before the exchange has closed and processed the day. The next scheduled slot will build it.</td></tr>
<tr><td class="l">Report says the DSE Market Report was not yet published</td><td class="l">The exchange posts its PDF some time after the close. The page is complete except participation, bond trades and bids/offers; a later run fills them in automatically.</td></tr>
<tr><td class="l">A fund row is missing</td><td class="l">That manager's website was unreachable or changed. The other rows are unaffected; the footer notes which source failed.</td></tr>
<tr><td class="l">PDF missing, web page present</td><td class="l">Chromium failed to start. Run <code>.venv\\Scripts\\python -m playwright install chromium</code> (Windows) or <code>.venv/bin/python -m playwright install chromium</code>, then <i>2 · Rebuild a date</i>.</td></tr>
<tr><td class="l">Nothing was built for days</td><td class="l">The computer was off at the scheduled times, or the DSE site was unreachable. Run the menu once by hand; the job also completes any recent partial day it finds.</td></tr>
</tbody></table>
<p>For anything else, read <code>~/.the-ticker/run.log</code>: every run writes what it did and why it stopped.</p>"""),
    ("files", "Where things live", """
<table class="data"><thead><tr><th class="l">Path</th><th class="l">Contents</th></tr></thead><tbody>
<tr><td class="l">market-report/index.html</td><td class="l">The newest report (becomes the live page if publishing is on)</td></tr>
<tr><td class="l">market-report/archive/&lt;date&gt;.html, .pdf</td><td class="l">Every report; archive/index.html lists them</td></tr>
<tr><td class="l">market-report/data/&lt;date&gt;.json</td><td class="l">The day's parsed dataset; history.json the 30-session series; state.json what was built last</td></tr>
<tr><td class="l">Desktop › The Ticker Market Reports</td><td class="l">Your copies: one PDF and one HTML per trading day</td></tr>
<tr><td class="l">scripts/market_report/</td><td class="l">The generator (Python). narrative.py holds the wording; render.py the design</td></tr>
<tr><td class="l">scripts/run_daily.*, scripts/schedule_*</td><td class="l">The runners and the scheduler installers</td></tr>
<tr><td class="l">scripts/.env</td><td class="l">Your settings (never committed)</td></tr>
</tbody></table>"""),
]


def write_guide(out_dir: Path) -> Path:
    toc = "".join(f'<a href="#{i}">{_e(t)}</a>' for i, t, _ in SECTIONS)
    body = "".join(
        f'<section id="{i}"><div class="sec-head"><span class="kicker"><b>{n:02d}</b>Guide</span><h2>{_e(t)}</h2></div>{b.replace("{site}", SITE)}</section>'
        for n, (i, t, b) in enumerate(SECTIONS, 1))
    extra = """
.steps{padding-left:22px; color:var(--ink2); display:grid; gap:10px; font-size:14.5px} .steps li b{color:var(--ink)}
pre{background:var(--card); border:1px solid var(--border); border-radius:8px; padding:12px 14px; font-family:var(--mono); font-size:12.5px; overflow-x:auto; color:var(--ink)}
code{font-family:var(--mono); font-size:.92em; background:var(--card2); border-radius:4px; padding:1px 5px}
.card .lbl{font-size:12.5px; font-weight:600; color:var(--ink2)} .card p.plain{margin-top:8px}
table.data td.l{color:var(--ink2); font-weight:400} table.data td:first-child.l{color:var(--ink); font-weight:600}
"""
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Guide · DSE Daily Market Report · The Ticker</title>
<meta name="viewport" content="width=device-width, initial-scale=1"><meta name="theme-color" content="#2c2015">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Poppins:wght@500;800&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>{CSS}{extra}</style></head><body>
<header class="mast"><div class="mast-in"><a class="wordmark" href="{SITE}" aria-label="The Ticker">{WORDMARK}</a>
<div class="mast-meta"><div class="tag">DAR ES SALAAM STOCK EXCHANGE · DAILY MARKET REPORT</div><h1>How the report is made, and how to run it</h1>
<div class="asof">A guide for whoever looks after the generator</div>
<div class="actions"><a class="btn" href="./index.html">Latest report</a><a class="btn ghost" href="archive/index.html">Past reports</a><a class="btn ghost" href="{SITE}">The Ticker home</a></div></div></div></header>
<nav class="nav" aria-label="Sections"><div class="nav-in">{toc}</div></nav>
<main>{body}</main>
<footer><div class="foot-bar">© <b>The Ticker</b> — all rights reserved.</div></footer></body></html>"""
    out = Path(out_dir) / "guide.html"
    out.write_text(html, encoding="utf-8")
    return out
