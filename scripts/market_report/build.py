"""Command-line entry point.

    python -m scripts.market_report.build            # build the last trading day if not built yet
    python -m scripts.market_report.build --date 2026-10-01 --force
    python -m scripts.market_report.build --no-pdf

Outputs (under --out, default market-report/):
    index.html                 latest report
    latest.pdf                 latest report as A4 PDF
    archive/YYYY-MM-DD.html    every report
    archive/YYYY-MM-DD.pdf
    archive/index.html         listing
    data/YYYY-MM-DD.json       the parsed dataset (machine-readable)
    data/history.json          rolling daily series for the trend tiles
    data/state.json            what was built last, and whether it was complete
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import date
from pathlib import Path

from .dse import DSE
from .model import Builder, load_json, save_json
from .render import render, render_archive
from .util import Http, iso, now_eat, parse_iso, short_date, tzs_compact

ROOT = Path(__file__).resolve().parents[2]


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


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
    # Allow pointing at a system/pre-installed Chromium (e.g. PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome)
    exe = os.environ.get("PLAYWRIGHT_CHROMIUM_PATH")
    if not exe:
        import glob
        cands = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))
        exe = cands[-1] if cands else None
    launch_kw = {"executable_path": exe} if exe and os.path.exists(exe) else {}
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(**launch_kw)
        except Exception:
            browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1120, "height": 1400})
        page.goto(html_path.resolve().as_uri(), wait_until="networkidle", timeout=90_000)
        page.emulate_media(media="print")
        page.wait_for_timeout(800)  # let web fonts settle
        page.pdf(path=str(pdf_path), format="A4", print_background=True, prefer_css_page_size=True,
                 display_header_footer=True, header_template=header, footer_template=footer,
                 margin={"top": "14mm", "bottom": "14mm", "left": "0", "right": "0"})
        browser.close()
    return True


def gh_output(**kv):
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a") as f:
        for k, v in kv.items():
            f.write(f"{k}={v}\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build The Ticker's DSE daily market report")
    ap.add_argument("--date", default="auto", help="YYYY-MM-DD or 'auto' (= DSE's last trading day)")
    ap.add_argument("--out", default=str(ROOT / "market-report"))
    ap.add_argument("--force", action="store_true", help="rebuild even if this day was already built")
    ap.add_argument("--no-pdf", action="store_true")
    args = ap.parse_args(argv)

    out = Path(args.out)
    data_dir = out / "data"
    arch_dir = out / "archive"
    arch_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    http = Http()
    dse = DSE(http)
    if args.date == "auto":
        d = dse.last_trade_date()
        log(f"DSE last trading day: {iso(d)} (now {now_eat():%Y-%m-%d %H:%M} EAT)")
    else:
        d = parse_iso(args.date)

    state = load_json(data_dir / "state.json", {})
    existing = load_json(data_dir / f"{iso(d)}.json", None)
    if existing and not args.force:
        if existing.get("sources", {}).get("dse_report_found"):
            log(f"{iso(d)} already built from the full DSE report; nothing to do")
            gh_output(built="false", date=iso(d))
            return 0
        log(f"{iso(d)} was built without the DSE Market Report; checking whether it is out now")

    builder = Builder(data_dir, http, log)
    try:
        ds = builder.build(d, prev_loader=lambda pd: load_json(data_dir / f"{iso(pd)}.json", None))
    except RuntimeError as e:
        log(f"not built: {e}")
        gh_output(built="false", date=iso(d))
        return 0
    if existing and not args.force and not ds["sources"]["dse_report_found"]:
        log("DSE Market Report still not published; keeping the existing build")
        gh_output(built="false", date=iso(d))
        return 0

    save_json(data_dir / f"{iso(d)}.json", ds)

    # archive index (newest first)
    archive = [x for x in load_json(data_dir / "archive.json", []) if x.get("date") != iso(d)]
    dsei = next((i for i in ds["indices"] if i["code"] == "DSEI"), None)
    blurb = f"turnover {tzs_compact(ds['totals']['turnover'])}" + (f" · DSEI {dsei['change_pct']:+.2f}%" if dsei and dsei.get("change_pct") is not None else "")
    pdf_name = f"{iso(d)}.pdf" if not args.no_pdf else None
    archive.insert(0, {"date": iso(d), "blurb": blurb, "pdf": bool(pdf_name), "complete": ds["sources"]["dse_report_found"]})
    archive.sort(key=lambda x: x["date"], reverse=True)

    html_latest = render(ds, archive, rel="", pdf_name=pdf_name)
    html_arch = render(ds, archive, rel="../", pdf_name=pdf_name)
    (out / "index.html").write_text(html_latest, encoding="utf-8")
    (arch_dir / f"{iso(d)}.html").write_text(html_arch, encoding="utf-8")
    (arch_dir / "index.html").write_text(render_archive(archive), encoding="utf-8")
    log(f"wrote {out/'index.html'} and {arch_dir/(iso(d)+'.html')}")

    pdf_ok = False
    if not args.no_pdf:
        try:
            pdf_ok = make_pdf(arch_dir / f"{iso(d)}.html", arch_dir / f"{iso(d)}.pdf", short_date(d))
            if pdf_ok:
                (out / "latest.pdf").write_bytes((arch_dir / f"{iso(d)}.pdf").read_bytes())
                log(f"wrote {arch_dir/(iso(d)+'.pdf')}")
        except Exception as e:  # noqa: BLE001
            log(f"PDF failed: {e}")
    if not pdf_ok:
        for x in archive:
            if x["date"] == iso(d):
                x["pdf"] = False
        # re-render without the PDF button
        (out / "index.html").write_text(render(ds, archive, rel="", pdf_name=None), encoding="utf-8")
        (arch_dir / f"{iso(d)}.html").write_text(render(ds, archive, rel="../", pdf_name=None), encoding="utf-8")
        (arch_dir / "index.html").write_text(render_archive(archive), encoding="utf-8")
    save_json(data_dir / "archive.json", archive)

    state.update({"last_built": iso(d), "complete": ds["sources"]["dse_report_found"], "built_at": ds["generated_at"]})
    save_json(data_dir / "state.json", state)
    log("summary: " + " | ".join([
        f"turnover {tzs_compact(ds['totals']['turnover'])}", f"deals {ds['totals']['deals']}",
        f"DSEI {dsei['close'] if dsei else '-'}", f"report {'full' if ds['sources']['dse_report_found'] else 'partial'}",
        f"funds {len(ds['cis'])}", f"notes {len(ds['notes'])}"]))
    for n in ds["notes"]:
        log(f"note: {n}")
    gh_output(built="true", date=iso(d), complete=str(ds["sources"]["dse_report_found"]).lower(),
              pdf=str(pdf_ok).lower(), summary=blurb)
    return 0


if __name__ == "__main__":
    sys.exit(main())
