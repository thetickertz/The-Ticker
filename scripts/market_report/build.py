"""Command-line entry point.

    python -m scripts.market_report.build            # build the last trading day if not built yet
    python -m scripts.market_report.build --date 2026-10-01 --force
    python -m scripts.market_report.build --no-pdf

Outputs (under --out, default market-report/):
    index.html                 the newest report
    archive/YYYY-MM-DD.html    every report
    archive/YYYY-MM-DD.pdf     A4 PDF (only for complete builds, i.e. once the exchange's own
                               Market Report was available; older PDFs are pruned, see --keep-pdf-days)
    archive/index.html         listing
    data/YYYY-MM-DD.json       the parsed dataset (machine-readable)
    data/history.json          rolling daily series for the trend tiles
    data/state.json            what was built last, and whether it was complete

Exit status is 0 both when something was built and when there was nothing to do; it is 1 only
when the pipeline itself failed AND the published report is falling behind (so the Actions job
turns red when it matters, not on every transient outage).
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path

from .dse import DSE
from .model import Builder, load_json, save_json
from .render import render, render_archive
from .util import Http, iso, now_eat, parse_iso, short_date, tzs_compact

ROOT = Path(__file__).resolve().parents[2]
MARKET_CLOSE_EAT = (16, 0)   # do not treat today's feed as final before this time (East Africa Time)
STALE_AFTER_DAYS = 4          # a failing pipeline turns the job red once the page is this many days behind
COMPLETE_LOOKBACK = 6         # how many recent archive entries to re-check for a late exchange report


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def gh_output(**kv):
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a") as f:
        for k, v in kv.items():
            f.write(f"{k}={v}\n")


# ───────────────────────────── PDF ─────────────────────────────
def make_pdf(html_path: Path, pdf_path: Path, title: str) -> bool:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("playwright not installed; skipping PDF")
        return False
    header = ('<div style="font-family:IBM Plex Sans,Arial,sans-serif;font-size:8px;color:#8f7e69;width:100%;'
              'padding:0 11mm;display:flex;justify-content:space-between"><span>The Ticker · DSE Daily Market Report</span>'
              f'<span>{title}</span></div>')
    footer = ('<div style="font-family:IBM Plex Sans,Arial,sans-serif;font-size:8px;color:#8f7e69;width:100%;'
              'padding:0 11mm;display:flex;justify-content:space-between"><span>thetickertz.github.io/The-Ticker · educational summary, not investment advice</span>'
              '<span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span></div>')
    # Allow pointing at a pre-installed Chromium (e.g. PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome)
    exe = os.environ.get("PLAYWRIGHT_CHROMIUM_PATH")
    if not exe:
        import glob
        cands = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))
        exe = cands[-1] if cands else None
    launch_kw = {"executable_path": exe} if exe and os.path.exists(exe) else {}
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(**launch_kw)
        except Exception:  # noqa: BLE001
            browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1120, "height": 1400})
        page.goto(html_path.resolve().as_uri(), wait_until="networkidle", timeout=90_000)
        page.emulate_media(media="print")
        page.wait_for_timeout(800)  # let web fonts settle
        kw = dict(path=str(pdf_path), format="A4", print_background=True, prefer_css_page_size=True,
                  display_header_footer=True, header_template=header, footer_template=footer,
                  margin={"top": "14mm", "bottom": "14mm", "left": "0", "right": "0"})
        try:
            page.pdf(tagged=True, outline=True, **kw)
        except TypeError:  # older Playwright without tagged/outline
            page.pdf(**kw)
        browser.close()
    return True


# ───────────────────────────── one day ─────────────────────────────
class Site:
    def __init__(self, out: Path, no_pdf: bool):
        self.out, self.no_pdf = out, no_pdf
        self.data_dir, self.arch_dir = out / "data", out / "archive"
        self.arch_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.archive: list[dict] = load_json(self.data_dir / "archive.json", [])
        self.state: dict = load_json(self.data_dir / "state.json", {})

    def newest(self) -> str | None:
        return max((x["date"] for x in self.archive), default=None)

    def entry(self, d: str) -> dict | None:
        return next((x for x in self.archive if x["date"] == d), None)

    def write_day(self, ds: dict) -> tuple[bool, bool]:
        """Render HTML (+PDF when complete) for one dataset. Returns (is_newest, pdf_ok)."""
        d = ds["date"]
        complete = bool(ds["sources"]["dse_report_found"])
        save_json(self.data_dir / f"{d}.json", ds)
        dsei = next((i for i in ds["indices"] if i["code"] == "DSEI"), None)
        blurb = f"turnover {tzs_compact(ds['totals']['turnover'])}" + (
            f" · DSEI {dsei['change_pct']:+.2f}%" if dsei and dsei.get("change_pct") is not None else "")
        self.archive = [x for x in self.archive if x["date"] != d]
        self.archive.insert(0, {"date": d, "blurb": blurb, "pdf": False, "complete": complete})
        self.archive.sort(key=lambda x: x["date"], reverse=True)
        is_newest = d >= (self.newest() or d)

        pdf_ok = False
        want_pdf = complete and not self.no_pdf
        pdf_name = f"{d}.pdf" if want_pdf else None
        html_arch = render(ds, self.archive, rel="../", pdf_name=pdf_name)
        (self.arch_dir / f"{d}.html").write_text(html_arch, encoding="utf-8")
        if want_pdf:
            try:
                pdf_ok = make_pdf(self.arch_dir / f"{d}.html", self.arch_dir / f"{d}.pdf", short_date(parse_iso(d)))
                log(f"wrote {self.arch_dir / (d + '.pdf')}")
            except Exception as e:  # noqa: BLE001
                log(f"PDF failed: {e}")
        if want_pdf and not pdf_ok:  # re-render without the PDF button
            pdf_name = None
            (self.arch_dir / f"{d}.html").write_text(render(ds, self.archive, rel="../", pdf_name=None), encoding="utf-8")
            (self.arch_dir / f"{d}.pdf").unlink(missing_ok=True)
        self.entry(d)["pdf"] = pdf_ok
        if is_newest:
            (self.out / "index.html").write_text(render(ds, self.archive, rel="", pdf_name=pdf_name), encoding="utf-8")
            self.state.update({"last_built": d, "complete": complete, "built_at": ds["generated_at"]})
        (self.arch_dir / "index.html").write_text(render_archive(self.archive), encoding="utf-8")
        log(f"wrote {self.arch_dir / (d + '.html')}" + (" and index.html" if is_newest else " (archive only; a newer day is live)"))
        return is_newest, pdf_ok

    def prune_pdfs(self, keep_days: int, today: date):
        if keep_days <= 0:
            return
        cutoff = iso(today - timedelta(days=keep_days))
        changed = False
        for x in self.archive:
            if x["date"] < cutoff and x.get("pdf"):
                (self.arch_dir / f"{x['date']}.pdf").unlink(missing_ok=True)
                x["pdf"] = False
                ds = load_json(self.data_dir / f"{x['date']}.json", None)
                if ds:  # drop the dead download button from that day's page
                    (self.arch_dir / f"{x['date']}.html").write_text(render(ds, self.archive, rel="../", pdf_name=None), encoding="utf-8")
                log(f"pruned {x['date']}.pdf")
                changed = True
        if changed:
            (self.arch_dir / "index.html").write_text(render_archive(self.archive), encoding="utf-8")

    def save(self):
        save_json(self.data_dir / "archive.json", self.archive)
        save_json(self.data_dir / "state.json", self.state)


def build_day(site: Site, builder: Builder, d: date, force: bool) -> dict | None:
    """Build one trading day if needed. Returns the dataset, or None when nothing was (re)built."""
    existing = load_json(site.data_dir / f"{iso(d)}.json", None)
    if existing and not force and existing.get("sources", {}).get("dse_report_found"):
        log(f"{iso(d)} already built from the full DSE report; nothing to do")
        return None
    if existing and not force:
        log(f"{iso(d)} was built without the DSE Market Report; checking whether it is out now")
        if not any(rd == d for rd, _ in builder.dse.daily_report_links()):
            log("DSE Market Report still not published; keeping the existing build")
            return None
    builder.notes.clear()
    ds = builder.build(d, prev_loader=lambda pd: load_json(site.data_dir / f"{iso(pd)}.json", None))
    if existing and not force and not ds["sources"]["dse_report_found"]:
        log("DSE Market Report could not be used; keeping the existing build")
        return None
    return ds


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build The Ticker's DSE daily market report")
    ap.add_argument("--date", default="auto", help="YYYY-MM-DD or 'auto' (= DSE's last trading day)")
    ap.add_argument("--out", default=str(ROOT / "market-report"))
    ap.add_argument("--force", action="store_true", help="rebuild even if this day was already built")
    ap.add_argument("--no-pdf", action="store_true")
    ap.add_argument("--keep-pdf-days", type=int, default=366,
                    help="delete archived PDFs older than this many days (HTML and JSON are kept forever)")
    args = ap.parse_args(argv)
    if not args.date or args.date.strip().lower() in ("", "auto"):
        args.date = "auto"

    site = Site(Path(args.out), args.no_pdf)
    http = Http()
    dse = DSE(http)
    builder = Builder(site.data_dir, http, log)
    outcome = {"built": "false", "date": "", "complete": "false", "pdf": "false", "summary": "", "reason": ""}
    try:
        if args.date == "auto":
            d = dse.last_trade_date()
            now = now_eat()
            log(f"DSE last trading day: {iso(d)} (now {now:%Y-%m-%d %H:%M} EAT)")
            if d == now.date() and (now.hour, now.minute) < MARKET_CLOSE_EAT and not args.force:
                log("today's session may still be open; the feed is not final yet — nothing built")
                outcome.update(date=iso(d), reason="session_open")
                gh_output(**outcome)
                return 0
        else:
            d = parse_iso(args.date)
        outcome["date"] = iso(d)

        ds = build_day(site, builder, d, args.force)
        if ds is None:
            outcome["reason"] = "up_to_date"
        else:
            is_newest, pdf_ok = site.write_day(ds)
            outcome.update(built="true", complete=str(ds["sources"]["dse_report_found"]).lower(), pdf=str(pdf_ok).lower(),
                           summary=site.entry(iso(d))["blurb"], reason="built")
            for n in ds["notes"]:
                log(f"note: {n}")

        # a Market Report that arrives after the next session: complete recent partial days too
        if args.date == "auto":
            pending = [x for x in site.archive[:COMPLETE_LOOKBACK] if not x.get("complete") and x["date"] != iso(d)]
            if pending:
                links = {rd: url for rd, url in builder.dse.daily_report_links() if rd}
                for x in pending:
                    pd_ = parse_iso(x["date"])
                    if pd_ in links:
                        log(f"completing {x['date']} now that its DSE Market Report is available")
                        try:
                            builder.notes.clear()
                            ds2 = builder.build(pd_, prev_loader=lambda q: load_json(site.data_dir / f"{iso(q)}.json", None))
                            if ds2["sources"]["dse_report_found"]:
                                site.write_day(ds2)
                                outcome["built"] = "true"
                        except Exception as e:  # noqa: BLE001
                            log(f"could not complete {x['date']}: {e}")

        site.prune_pdfs(args.keep_pdf_days, d)
        site.save()
        if ds is not None:
            dsei = next((i for i in ds["indices"] if i["code"] == "DSEI"), None)
            log("summary: " + " | ".join([
                f"turnover {tzs_compact(ds['totals']['turnover'])}", f"deals {ds['totals'].get('deals')}",
                f"DSEI {dsei['close'] if dsei else '-'}", f"report {'full' if ds['sources']['dse_report_found'] else 'partial'}",
                f"funds {len(ds['cis'])}", f"notes {len(ds['notes'])}"]))
        gh_output(**outcome)
        return 0
    except Exception as e:  # noqa: BLE001 - a source outage must not leave the repo half-written
        log(f"build failed: {e}")
        traceback.print_exc()
        outcome["reason"] = "error"
        gh_output(**outcome)
        last = site.state.get("last_built")
        behind = (date.today() - parse_iso(last)).days if last else None
        if behind is not None and behind > STALE_AFTER_DAYS:
            log(f"the published report is {behind} days old — failing the job so someone looks")
            return 1
        return 0


if __name__ == "__main__":
    sys.exit(main())
