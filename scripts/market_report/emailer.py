"""E-mail the finished report (PDF attached, one-minute summary in the body).

Settings come from environment variables (the runners load scripts/.env):
    REPORT_SMTP_HOST, REPORT_SMTP_PORT (587), REPORT_SMTP_USER, REPORT_SMTP_PASS,
    REPORT_EMAIL_FROM, REPORT_EMAIL_TO (comma-separated)
Recipients can also be listed one per line in scripts/recipients.txt (lines starting with # are
ignored); both sources are merged. An empty variable counts as unset.

    python -m scripts.market_report.emailer            # send the report named by REPORT_DATE or the last built day
    python -m scripts.market_report.emailer --test     # same, but says so in the subject (use to check the set-up)
    python -m scripts.market_report.emailer --to you@example.com   # one-off recipient(s) instead of the list
"""
from __future__ import annotations

import argparse
import os
import re
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path

from .model import load_json
from .narrative import summary_bullets
from .util import human_date, parse_iso, short_date

ROOT = Path(__file__).resolve().parents[2]
RECIPIENTS_FILE = ROOT / "scripts" / "recipients.txt"


def env(k, default=None):
    return (os.environ.get(k) or "").strip() or default  # '' counts as unset


def recipients(only: str | None = None) -> list[str]:
    """The configured list (REPORT_EMAIL_TO + scripts/recipients.txt), or just `only` when given."""
    seen, out = set(), []
    sources = [only] if only else [env("REPORT_EMAIL_TO", "")]
    if not only and RECIPIENTS_FILE.exists():
        sources.append(",".join(l.strip() for l in RECIPIENTS_FILE.read_text().splitlines()
                                if l.strip() and not l.strip().startswith("#")))
    for src in sources:
        for addr in re.split(r"[,\s;]+", src):
            a = addr.strip()
            if a and "@" in a and a.lower() not in seen:
                seen.add(a.lower())
                out.append(a)
    return out


def smtp_configured() -> bool:
    return bool(env("REPORT_SMTP_HOST"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="E-mail The Ticker's DSE daily market report")
    ap.add_argument("--test", action="store_true", help="mark the subject as a test send")
    ap.add_argument("--to", default=None, help="send only to these comma-separated addresses")
    ap.add_argument("--date", default=None, help="YYYY-MM-DD (default: REPORT_DATE or the last built day)")
    args = ap.parse_args(argv)

    out = Path(env("REPORT_OUT", str(ROOT / "market-report")))
    state = load_json(out / "data" / "state.json", {})
    d = args.date or env("REPORT_DATE") or state.get("last_built")
    if not d:
        print("nothing built yet — run the report first")
        return 1
    host = env("REPORT_SMTP_HOST")
    to = recipients(args.to)
    if not host:
        print("e-mail not configured: set REPORT_SMTP_HOST (and user/password) in scripts/.env")
        return 2
    if not to:
        print("no recipients: set REPORT_EMAIL_TO in scripts/.env or add addresses to scripts/recipients.txt")
        return 2
    ds = load_json(out / "data" / f"{d}.json", None)
    if not ds:
        print(f"dataset for {d} is missing")
        return 1
    dd = parse_iso(d)
    complete = bool(ds.get("sources", {}).get("dse_report_found"))

    msg = EmailMessage()
    subject = f"The Ticker · DSE Daily Market Report · {short_date(dd)}"
    if not complete:
        subject += " (preliminary)"
    if args.test:
        subject = "[TEST] " + subject
    msg["Subject"] = subject
    msg["From"] = env("REPORT_EMAIL_FROM") or env("REPORT_SMTP_USER") or "the-ticker@example.com"
    msg["To"] = ", ".join(to)
    bullets = [re.sub(r"<[^>]+>", "", b) for b in summary_bullets(ds)]
    url = "https://thetickertz.github.io/The-Ticker/market-report/"
    note = "" if complete else ("\nThis is a preliminary edition: the exchange had not yet published its own Market Report, "
                                "so foreign-participation and bond-trade details follow in the final edition.\n")
    body = (f"DSE Daily Market Report — {human_date(dd)}\n\n" + "\n".join(f"• {b}" for b in bullets) + "\n" + note
            + "\nThe full report is attached as a PDF.\n\nThe Ticker — educational summary, not investment advice.")
    msg.set_content(body)
    html_bits = "".join(f"<li style='margin-bottom:6px'>{b}</li>" for b in summary_bullets(ds))
    html_note = "" if complete else "<p style='color:#8f7e69'><i>Preliminary edition: foreign-participation and bond-trade details follow in the final edition.</i></p>"
    msg.add_alternative(
        f"<html><body style='font-family:Arial,Helvetica,sans-serif;color:#2b2119;max-width:680px'>"
        f"<div style='background:#2c2015;color:#f8f2e9;padding:18px 22px;border-radius:10px'>"
        f"<div style='font-size:12px;letter-spacing:.14em;color:#c9b8a2'>THE TICKER · DSE DAILY MARKET REPORT</div>"
        f"<div style='font-size:22px;font-weight:700;margin-top:6px'>Market close, {human_date(dd)}</div></div>"
        f"<h3 style='margin:18px 0 6px'>The session in one minute</h3><ul style='padding-left:20px;line-height:1.5'>{html_bits}</ul>{html_note}"
        f"<p>The full report is attached as a PDF.</p>"
        f"<p style='font-size:12px;color:#8f7e69'>Produced automatically from DSE, Bank of Tanzania and fund-manager publications. "
        f"Educational summary, not investment advice.</p></body></html>", subtype="html")
    pdf = out / "archive" / f"{d}.pdf"
    if pdf.exists():
        msg.add_attachment(pdf.read_bytes(), maintype="application", subtype="pdf",
                           filename=f"The Ticker - DSE Daily Market Report - {d}{'' if complete else ' (preliminary)'}.pdf")
    else:
        print(f"warning: {pdf} not found; sending the summary without the attachment")

    port = int(env("REPORT_SMTP_PORT", "587"))
    server = smtplib.SMTP_SSL(host, port, timeout=60) if port == 465 else smtplib.SMTP(host, port, timeout=60)
    with server as s:
        s.ehlo()
        if port != 465 and s.has_extn("starttls"):
            s.starttls()
            s.ehlo()
        user, pw = env("REPORT_SMTP_USER"), env("REPORT_SMTP_PASS")
        if user and pw:
            s.login(user, pw)
        s.send_message(msg)
    print(f"sent '{subject}' to {', '.join(to)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
