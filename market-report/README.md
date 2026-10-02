# DSE Daily Market Report — automated pipeline

The Ticker's daily report on the Dar es Salaam Stock Exchange, modelled on the daily
"Capital Markets Update" that brokerage desks circulate, but rebuilt in The Ticker's design and
written so a first-time investor can follow it. **It is produced entirely by code on a schedule on
your own computer; nobody (and no AI model, and no cloud service) is in the loop on a normal day.**

Live page: <https://thetickertz.github.io/The-Ticker/market-report/> · archive at `archive/`
(each day's page has a *Download PDF* button).

## What is in the report

| Section | Source | How it is derived |
|---|---|---|
| Today in one minute, key numbers tape, trend tiles | DSE JSON feed + 30-day history we keep in `data/history.json` | Rule-based sentences generated from the numbers |
| Key market indicators (turnover, volume, deals, market caps, five indices) today vs previous session | DSE JSON feed (`/api/get/market/prices/for/range`, `/get/last/traded/indices`) | Market caps are summed per counter; domestic = excluding the six cross-listed counters; ETF cap from the DSE Market Report |
| Top movers (share of turnover), top three gainers and losers, breadth | DSE JSON feed | Change = close vs previous close, as the exchange reports it; only counters that actually traded on the DSE count (cross-listed counters repriced from Nairobi with no local deal are listed separately) |
| Foreign vs local participation (equities and ETFs), net foreign flow | **DSE Market Report** of the day (the PDF the exchange posts on its homepage, served as HTML) | Parsed from the "Equities/ETF Market Turnover" tables |
| Bonds traded by term: deals, turnover, weighted-average price, clean price and yield | DSE Market Report "Daily Price Information" table | Weighted by face value traded; Treasury bonds only (numeric bond numbers) — infrastructure/corporate lines are listed separately |
| Latest Treasury bond and Treasury bill auction | Bank of Tanzania (`/TBonds/AuctionSummaries`, `/Tbills/getTbillsDetails`) | Bid-to-cover = tendered ÷ offered; BOT auction prices are clean prices |
| Unit trusts (NAV, daily, YTD, annualised) | UTT AMIS (6 funds), Orbit Securities (Inuka ×2), Watumishi Housing (Faida) | YTD vs last valuation of the previous year; annualised = YTD × 365 ÷ days elapsed |
| Full equities table (prev close, close, change, year start, YTD, turnover, deals, bids, offers, volume, market cap) and ETFs | DSE JSON feed + DSE Market Report (bids/offers, suspended counters) + cached year-start prices | Year-start price = last close of the previous year, adjusted for a share split when the share count changed by an integer ratio *and* the price stepped by the same ratio on one day (NMB 10-for-1 in 2026) |
| Glossary, sources, disclaimer | static | — |

Everything in the report is traceable: `data/YYYY-MM-DD.json` holds the exact parsed dataset
for each day, and the footer links to the official publications.

## How the automation runs — from your own computer

Nothing here depends on Claude, GitHub Actions or any other service: it is a Python program that
reads public websites and writes files. Your computer runs it on a timer, and (if you choose) pushes
the result to GitHub so the public page updates.

**One-time setup (10 minutes)**

1. Install [Python 3.11+](https://www.python.org/downloads/) (on Windows tick *Add python.exe to PATH*)
   and [Git](https://git-scm.com/downloads). Make sure `git push` works from your terminal for this
   repository (GitHub Desktop or `gh auth login` sets the credentials up).
2. Clone the repository and open a terminal in it:
   `git clone https://github.com/thetickertz/The-Ticker.git && cd The-Ticker`
3. Copy `scripts/.env.example` to `scripts/.env`. Keep `REPORT_PUSH=1` to publish to GitHub Pages, or
   set it to `0` to only build the files locally. Fill in the SMTP lines only if you want the PDF
   e-mailed.
4. Run it once by hand to let it install its own virtual environment and Chromium (first run ~3 minutes):
   - Windows: `powershell -ExecutionPolicy Bypass -File scripts\run_daily.ps1`
   - macOS / Linux: `scripts/run_daily.sh`
   The report appears in `market-report/` (open `market-report/index.html`), and with `REPORT_PUSH=1`
   it is committed and pushed.
5. Install the schedule (weekdays 16:40, 18:40, 20:40 and next-morning 08:10, East Africa Time —
   converted to your computer's time zone automatically):
   - Windows: `powershell -ExecutionPolicy Bypass -File scripts\schedule_windows.ps1`
     (creates a Task Scheduler job named *The Ticker - DSE Daily Market Report*; it wakes the PC and
     catches up if a start was missed; `-Remove` deletes it)
   - macOS / Linux: `scripts/schedule_unix.sh` (adds four cron lines; `--remove` deletes them)

Each run: pulls the latest repository, asks the DSE for its last trading day, builds only if that day
is not yet built from the full exchange report, writes `archive/<date>.html`, `data/<date>.json`,
the PDF (only once the exchange's own Market Report is available), updates `archive/index.html`,
rewrites `index.html` when the day is the newest, re-checks the last few days for a partial build
whose Market Report has since appeared, then commits and pushes (if `REPORT_PUSH=1`) and e-mails
(if SMTP is configured). Logs go to `~/.the-ticker/run.log` (Windows: `%USERPROFILE%\.the-ticker\run.log`).

If the exchange has not yet posted its Market Report when a run happens, the page is still built
from the JSON feed (all prices, indices, movers, auctions and funds), with a note that participation
and bond-trade details will be filled in; a later run completes it. In `auto` mode nothing is built
before 16:00 EAT on the trading day itself, so an intraday snapshot is never published. The computer
needs to be on (or allowed to wake) at the scheduled times; a missed slot is simply picked up by the
next one.

Manual runs: `scripts/run_daily.sh --date 2026-10-01 --force` (Windows: `-Date 2026-10-01 -Force`), or
the underlying command `python -m scripts.market_report.build --date 2026-10-01 --force --no-pdf`.

### Alternative: run it on GitHub's servers

`.github/workflows/market-report.yml` does the same job in GitHub Actions and is kept as an option
with its schedule switched off. Uncomment the `schedule:` block to use it instead of (or as a backup
to) your computer; it can also be started by hand from the Actions tab. Both are idempotent, so
running both is safe, just redundant.

## Optional: e-mail distribution

Fill in the SMTP lines of `scripts/.env` (or, for the GitHub Actions alternative, add them as repository
secrets) and every *complete* build that produced a PDF is e-mailed with the PDF attached and the
one-minute summary in the body: `REPORT_SMTP_HOST`, `REPORT_SMTP_PORT` (587), `REPORT_SMTP_USER`,
`REPORT_SMTP_PASS`, `REPORT_EMAIL_FROM`, `REPORT_EMAIL_TO` (comma-separated). Without them the step
is skipped. (Gmail works with an app password; Microsoft 365 with SMTP AUTH enabled.)

## Code map (`scripts/market_report/`)

| File | Role |
|---|---|
| `dse.py` | DSE JSON endpoints, homepage report-link discovery, Market Report parser (pdf2htmlEX text → tables) |
| `bot.py` | Bank of Tanzania bond and T-bill auction results |
| `cis.py` | Fund-manager NAV scrapers (each independent; a broken one only drops its rows) |
| `model.py` | Assembles the day's dataset, derives indicators, movers, bonds-by-term, history backfill |
| `narrative.py` | Plain-language explanations generated from the numbers |
| `charts.py` | Inline SVG charts (thin marks, one axis, text in text colours) |
| `render.py` | The HTML page in The Ticker's design, with print CSS for the A4 PDF |
| `build.py` | CLI entry point, idempotency, PDF via headless Chromium (Playwright) |
| `emailer.py` | Optional SMTP distribution |
| `../run_daily.sh`, `../run_daily.ps1` | Local runners (set-up, pull, build, commit, push, e-mail) for macOS/Linux and Windows |
| `../schedule_unix.sh`, `../schedule_windows.ps1` | Install or remove the schedule (cron / Task Scheduler) |

## Known limits and how to extend

- **Fund coverage.** Only managers with a machine-readable NAV page are included (UTT AMIS, Orbit's
  Inuka funds, WHI's Faida Fund). Imara/Kesho Tulivu (TSL), iDollar (iTrust), SanlamAllianz Pesa and
  the ETF NAVs are not published in a scrapable form today; add a function in `cis.py` returning the
  same dict shape and append it to `collect()`.
- **DSE Market Report format.** The parser keys off the report's table headers. If the exchange
  changes the layout, the page still builds from the JSON feed and the footer "Build notes" says what
  was skipped; fix `parse_report()` in `dse.py` and re-run with `--force`.
- **Holidays.** The build keys off the DSE's own last-trading-day endpoint, so public holidays need no
  calendar.
- **Repository size.** Each complete day adds roughly 400 KB to the working tree (HTML + JSON + one PDF),
  and because git keeps history the repository itself grows by about that much per trading day
  (~100 MB a year). PDFs older than a year are removed from the working tree (`--keep-pdf-days`, default
  366) and their pages re-rendered without the download button; the HTML page and JSON dataset for every
  day are kept, so the archive stays complete. If the history ever becomes a burden, move the PDFs to a
  release asset or an object store — the pipeline only needs `archive/<date>.pdf` to exist when it writes
  the button.
- **Branding/narrative changes.** Text templates live in `narrative.py`; layout and CSS in `render.py`.
