"""A small menu so the daily report can be run without typing commands.

    python scripts/ticker.py          (or double-click Ticker-Report.bat / Ticker-Report.command)
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WIN = platform.system() == "Windows"
if platform.system() == "Darwin" and shutil.which("xattr"):
    # a downloaded copy is "quarantined" and Finder refuses to open Ticker-Report.command; clear the flag
    subprocess.call(["xattr", "-dr", "com.apple.quarantine", str(ROOT / "Ticker-Report.command"), str(ROOT / "scripts")],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
SITE = "https://thetickertz.github.io/The-Ticker/market-report/"


def runner(*extra: str) -> int:
    if WIN:
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts" / "run_daily.ps1"), *extra]
    else:
        cmd = ["bash", str(ROOT / "scripts" / "run_daily.sh"), *extra]
    return subprocess.call(cmd, cwd=ROOT)


def open_path(p: Path | str):
    p = str(p)
    if WIN:
        os.startfile(p)  # type: ignore[attr-defined]
    elif platform.system() == "Darwin":
        subprocess.call(["open", p])
    else:
        subprocess.call(["xdg-open", p])


def export_dir() -> Path | None:
    sys.path.insert(0, str(ROOT))
    try:
        from scripts.market_report.build import export_dir as _ed  # noqa: PLC0415
        return _ed()
    except Exception:  # noqa: BLE001
        return None


def load_env():
    env = ROOT / "scripts" / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


RECIPIENTS = ROOT / "scripts" / "recipients.txt"


def read_recipients() -> list[str]:
    if not RECIPIENTS.exists():
        return []
    return [l.strip() for l in RECIPIENTS.read_text().splitlines() if l.strip() and not l.strip().startswith("#")]


def write_recipients(addrs: list[str]):
    RECIPIENTS.write_text("# One e-mail address per line. Lines starting with # are ignored.\n" + "\n".join(addrs) + ("\n" if addrs else ""))


def manage_recipients():
    while True:
        addrs = read_recipients()
        env_to = [a.strip() for a in (os.environ.get("REPORT_EMAIL_TO") or "").split(",") if a.strip()]
        print("\n  Recipients list (scripts/recipients.txt):")
        for i, a in enumerate(addrs, 1):
            print(f"   {i}. {a}")
        if not addrs:
            print("   (empty)")
        if env_to:
            print("  Also from scripts/.env REPORT_EMAIL_TO: " + ", ".join(env_to))
        print("\n  a  Add an address    r  Remove an address    b  Back")
        c = input("  Choose: ").strip().lower()
        if c == "a":
            a = input("  E-mail address to add: ").strip()
            if "@" in a and a.lower() not in [x.lower() for x in addrs]:
                write_recipients(addrs + [a])
                print(f"  added {a}")
            else:
                print("  not added (invalid or already listed)")
        elif c == "r":
            n = input("  Number to remove: ").strip()
            if n.isdigit() and 1 <= int(n) <= len(addrs):
                removed = addrs.pop(int(n) - 1)
                write_recipients(addrs)
                print(f"  removed {removed}")
        else:
            return


def menu():
    load_env()
    while True:
        print("\n  The Ticker · DSE Daily Market Report")
        print("  ───────────────────────────────────")
        print("  1  Build / refresh the latest trading day")
        print("  2  Rebuild a specific date")
        print("  3  Open the latest report")
        print("  4  Open the Desktop folder of reports")
        print("  5  Install or remove the schedule")
        print("  6  Open the guide")
        print("  7  Show settings")
        print("  8  E-mail recipients (list / add / remove)")
        print("  9  Send a test e-mail of the latest report now")
        print("  U  Update the generator from GitHub (keeps your settings and reports)")
        print("  0  Quit")
        choice = input("\n  Choose: ").strip()
        if choice == "1":
            runner()
        elif choice == "2":
            d = input("  Date (YYYY-MM-DD): ").strip()
            if len(d) == 10:
                runner("-Date", d, "-Force") if WIN else runner("--date", d, "--force")
        elif choice == "3":
            page = ROOT / "market-report" / "index.html"
            open_path(page) if page.exists() else print("  No report built yet — choose 1 first.")
        elif choice == "4":
            ed = export_dir()
            if ed and ed.exists():
                open_path(ed)
            else:
                print(f"  The folder does not exist yet ({ed}); it is created by the first finished report.")
        elif choice == "5":
            sub = input("  (i)nstall or (r)emove? ").strip().lower()
            extra = []
            if not sub.startswith("r"):
                t = input("  Time of day in East Africa Time, Monday to Friday [18:30]: ").strip() or "18:30"
                extra = (["-Time", t] if WIN else ["--time", t])
            if WIN:
                args = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts" / "schedule_windows.ps1")]
                subprocess.call(args + (["-Remove"] if sub.startswith("r") else extra), cwd=ROOT)
            else:
                subprocess.call(["bash", str(ROOT / "scripts" / "schedule_unix.sh")] + (["--remove"] if sub.startswith("r") else extra), cwd=ROOT)
        elif choice == "6":
            g = ROOT / "market-report" / "guide.html"
            open_path(g) if g.exists() else webbrowser.open(SITE + "guide.html")
        elif choice == "7":
            env = ROOT / "scripts" / ".env"
            print(f"\n  Settings file: {env} ({'exists' if env.exists() else 'missing — copy scripts/.env.example to scripts/.env'})")
            for k in ("REPORT_PUSH", "REPORT_EXPORT_DIR", "REPORT_SMTP_HOST", "REPORT_SMTP_USER", "REPORT_EMAIL_TO"):
                print(f"  {k:<18} = {os.environ.get(k, '') or '(default)'}")
            print(f"  E-mail             = {'configured' if os.environ.get('REPORT_SMTP_HOST') else 'not set up'}; recipients file has {len(read_recipients())} address(es)")
            print(f"  Reports folder     = {export_dir()}")
            print(f"  Log                = {Path.home() / '.the-ticker' / 'run.log'}")
        elif choice == "8":
            manage_recipients()
        elif choice == "9":
            if not os.environ.get("REPORT_SMTP_HOST"):
                print("  E-mail is not set up yet. Fill in the REPORT_SMTP_* lines in scripts/.env (see the guide, section 'E-mail delivery').")
            else:
                py = ROOT / (".venv/Scripts/python.exe" if WIN else ".venv/bin/python")
                extra = input("  Send to (leave empty for the recipients list): ").strip()
                cmd = [str(py if py.exists() else sys.executable), "-m", "scripts.market_report.emailer", "--test"] + (["--to", extra] if extra else [])
                subprocess.call(cmd, cwd=ROOT)
        elif choice.lower() == "u":
            subprocess.call([sys.executable, str(ROOT / "scripts" / "update.py")], cwd=ROOT)
            print("  Restart the menu to use the updated version.")
            return 0
        elif choice in ("0", "q", ""):
            return 0
        else:
            print("  Not a choice.")


if __name__ == "__main__":
    try:
        sys.exit(menu())
    except KeyboardInterrupt:
        sys.exit(0)
