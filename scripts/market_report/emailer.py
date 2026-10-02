"""Optional e-mail distribution of the finished report (PDF attached, summary in the body).

Configured entirely through environment variables so the GitHub Actions step can be skipped
when they are absent:
    REPORT_SMTP_HOST, REPORT_SMTP_PORT (default 587), REPORT_SMTP_USER, REPORT_SMTP_PASS,
    REPORT_EMAIL_FROM, REPORT_EMAIL_TO (comma-separated)
"""
from __future__ import annotations

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


def main(argv=None) -> int:
    out = Path(os.environ.get("REPORT_OUT", ROOT / "market-report"))
    state = load_json(out / "data" / "state.json", {})
    d = state.get("last_built")
    if not d:
        print("nothing built yet")
        return 0
    host, to = os.environ.get("REPORT_SMTP_HOST"), os.environ.get("REPORT_EMAIL_TO")
    if not host or not to:
        print("e-mail not configured (REPORT_SMTP_HOST / REPORT_EMAIL_TO missing); skipping")
        return 0
    ds = load_json(out / "data" / f"{d}.json", None)
    if not ds:
        print("dataset missing")
        return 1
    dd = parse_iso(d)
    msg = EmailMessage()
    msg["Subject"] = f"The Ticker · DSE Daily Market Report · {short_date(dd)}"
    msg["From"] = os.environ.get("REPORT_EMAIL_FROM", os.environ.get("REPORT_SMTP_USER", "the-ticker@example.com"))
    msg["To"] = to
    bullets = [re.sub(r"<[^>]+>", "", b) for b in summary_bullets(ds)]
    url = "https://thetickertz.github.io/The-Ticker/market-report/"
    body = (f"DSE Daily Market Report — {human_date(dd)}\n\n" + "\n".join(f"• {b}" for b in bullets)
            + f"\n\nFull report: {url}\nArchive: {url}archive/\n\nThe Ticker — educational summary, not investment advice.")
    msg.set_content(body)
    html_bits = "".join(f"<li>{b}</li>" for b in summary_bullets(ds))
    msg.add_alternative(f"<html><body style='font-family:Arial,sans-serif;color:#2b2119'><h2 style='margin:0 0 4px'>DSE Daily Market Report</h2>"
                        f"<div style='color:#8f7e69;margin-bottom:12px'>{human_date(dd)} · The Ticker</div><ul>{html_bits}</ul>"
                        f"<p><a href='{url}'>Open the full report</a> · <a href='{url}archive/'>Archive</a></p>"
                        f"<p style='font-size:12px;color:#8f7e69'>Educational summary, not investment advice.</p></body></html>", subtype="html")
    pdf = out / "archive" / f"{d}.pdf"
    if pdf.exists():
        msg.add_attachment(pdf.read_bytes(), maintype="application", subtype="pdf",
                           filename=f"The-Ticker-DSE-Daily-Market-Report-{d}.pdf")
    port = int(os.environ.get("REPORT_SMTP_PORT", "587"))
    if port == 465:  # implicit TLS
        server = smtplib.SMTP_SSL(host, port, timeout=60)
    else:
        server = smtplib.SMTP(host, port, timeout=60)
    with server as s:
        s.ehlo()
        if port != 465 and s.has_extn("starttls"):
            s.starttls()
            s.ehlo()
        user, pw = os.environ.get("REPORT_SMTP_USER"), os.environ.get("REPORT_SMTP_PASS")
        if user and pw:
            s.login(user, pw)
        s.send_message(msg)
    print(f"sent to {to}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
