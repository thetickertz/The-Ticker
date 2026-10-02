# DSE Daily Market Report — automated pipeline

The Ticker's daily report on the Dar es Salaam Stock Exchange, modelled on the daily
"Capital Markets Update" that brokerage desks circulate, but rebuilt in The Ticker's design and
written so a first-time investor can follow it. **It is produced entirely by code on a schedule;
nobody (and no AI model) is in the loop on a normal day.**

Live page: <https://thetickertz.github.io/The-Ticker/market-report/> · archive at `archive/`
· PDF at `latest.pdf`.

## What is in the report

| Section | Source | How it is derived |
|---|---|---|
| Today in one minute, key numbers tape, trend tiles | DSE JSON feed + 30-day history we keep in `data/history.json` | Rule-based sentences generated from the numbers |
| Key market indicators (turnover, volume, deals, market caps, five indices) today vs previous session | DSE JSON feed (`/api/get/market/prices/for/range`, `/get/last/traded/indices`) | Market caps are summed per counter; domestic = excluding the six cross-listed counters; ETF cap from the DSE Market Report |
| Top movers (share of turnover), top three gainers and losers | DSE JSON feed | Change = close vs previous close, as the exchange reports it |
| Foreign vs local participation (equities and ETFs), net foreign flow | **DSE Market Report** of the day (the PDF the exchange posts on its homepage, served as HTML) | Parsed from the "Equities/ETF Market Turnover" tables |
| Bonds traded by term: deals, turnover, weighted-average price and yield | DSE Market Report "Daily Price Information" table | Weighted by face value traded |
| Latest Treasury bond and Treasury bill auction | Bank of Tanzania (`/TBonds/AuctionSummaries`, `/Tbills/getTbillsDetails`) | Bid-to-cover = tendered ÷ offered |
| Unit trusts (NAV, daily, YTD, annualised) | UTT AMIS (6 funds), Orbit Securities (Inuka ×2), Watumishi Housing (Faida) | YTD vs last valuation of the previous year; annualised = YTD × 365 ÷ days elapsed |
| Full equities table (prev close, close, change, year start, YTD, turnover, deals, bids, offers, volume, market cap) and ETFs | DSE JSON feed + DSE Market Report (bids/offers) + cached year-start prices | Year-start price = last close of the previous year, fetched once per counter per year |
| Glossary, sources, disclaimer | static | — |

Everything in the report is traceable: `data/YYYY-MM-DD.json` holds the exact parsed dataset
for each day, and the footer links to the official publications.

## How the automation runs

`.github/workflows/market-report.yml` runs on GitHub Actions every weekday at 16:40, 18:40 and
20:40 East Africa Time, plus a catch-up at 08:10 the next morning. Each run:

1. asks the DSE for its last trading day;
2. skips if that day was already built from the full DSE Market Report (so the extra slots cost nothing);
3. otherwise fetches everything, writes `index.html`, `archive/<date>.html`, `archive/<date>.pdf`,
   `latest.pdf`, `data/<date>.json`, and updates `archive/index.html`;
4. commits to `main`, which GitHub Pages publishes within a minute or two.

If the exchange has not yet posted its Market Report when a run happens, the page is still
built from the JSON feed (all prices, indices, movers, auctions and funds), with a note that
participation and bond-trade details will be filled in; the next scheduled run completes it.

Manual run: **Actions → "DSE daily market report" → Run workflow** (optionally with a date and
*force*). Locally:

```bash
pip install -r scripts/requirements.txt && python -m playwright install chromium
python -m scripts.market_report.build                 # last trading day
python -m scripts.market_report.build --date 2026-10-01 --force --no-pdf
```

## Optional: e-mail distribution

Add these repository secrets and every *complete* build is e-mailed with the PDF attached and the
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
- **Branding/narrative changes.** Text templates live in `narrative.py`; layout and CSS in `render.py`.
