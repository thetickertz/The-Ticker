"""Update the generator in place from GitHub, keeping your settings, e-mail list, reports and the
Python environment.

    python3 scripts/update.py              (or menu choice U)
    curl -L https://raw.githubusercontent.com/thetickertz/The-Ticker/main/scripts/update.py | python3 -

It downloads the project ZIP for the branch named in scripts/SOURCE_BRANCH (falling back to main),
replaces the program files (scripts/, Ticker-Report.*, market-report/README.md) and refreshes the
Python packages. It never touches scripts/.env, scripts/recipients.txt, .venv or market-report/data,
archive and index.html.
"""
from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

REPO = "thetickertz/The-Ticker"
FALLBACK_BRANCHES = ["main", "claude/automated-market-report-i53qpm"]  # tried in order; first one that contains the generator wins
KEEP = {"scripts/.env", "scripts/recipients.txt"}
REPLACE_DIRS = ["scripts"]
REPLACE_FILES = ["Ticker-Report.bat", "Ticker-Report.command", "market-report/README.md"]


def project_root() -> Path:
    here = Path(__file__).resolve().parent.parent if "__file__" in globals() and Path(__file__).exists() else Path.cwd()
    for cand in (here, Path.cwd()):
        if (cand / "scripts" / "market_report").exists() or (cand / "scripts").exists():
            return cand
    return Path.cwd()


def unquarantine(root: Path) -> None:
    """macOS marks files that came from a browser download (or a ZIP of one) as quarantined, and
    Finder then refuses to open Ticker-Report.command ("Apple could not verify ... is free of
    malware"). Clearing the flag on the program files is what the user would otherwise do by hand."""
    if sys.platform != "darwin" or not shutil.which("xattr"):
        return
    targets = [str(root / f) for f in REPLACE_FILES if (root / f).exists()] + [str(root / d) for d in REPLACE_DIRS if (root / d).exists()]
    subprocess.call(["xattr", "-dr", "com.apple.quarantine", *targets], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def download(branch: str) -> bytes | None:
    """Fetch the branch ZIP. python.org builds of Python on macOS cannot verify certificates until
    'Install Certificates.command' has been run, so fall back to the system's curl, then to the
    project's own Python environment (which bundles certificates via requests)."""
    url = f"https://github.com/{REPO}/archive/refs/heads/{branch}.zip"
    errors = []
    try:
        with urllib.request.urlopen(url, timeout=120) as r:
            return r.read()
    except Exception as e:  # noqa: BLE001
        errors.append(f"python: {e}")
    if shutil.which("curl"):
        try:
            r = subprocess.run(["curl", "-fsSL", "--max-time", "180", url], capture_output=True, timeout=200)
            if r.returncode == 0 and r.stdout[:2] == b"PK":
                return r.stdout
            errors.append(f"curl: exit {r.returncode}")
        except Exception as e:  # noqa: BLE001
            errors.append(f"curl: {e}")
    root = project_root()
    py = root / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
    if py.exists():
        try:
            r = subprocess.run([str(py), "-c", "import requests,sys;sys.stdout.buffer.write(requests.get(sys.argv[1],timeout=180).content)", url],
                               capture_output=True, timeout=240)
            if r.returncode == 0 and r.stdout[:2] == b"PK":
                return r.stdout
            errors.append("venv: " + r.stderr.decode(errors="ignore")[-120:])
        except Exception as e:  # noqa: BLE001
            errors.append(f"venv: {e}")
    print(f"  could not download {branch}: " + " | ".join(errors))
    return None


def main() -> int:
    root = project_root()
    print(f"Updating the generator in {root}")
    branches = [a for a in sys.argv[1:] if a and not a.startswith("-")]
    sb = root / "scripts" / "SOURCE_BRANCH"
    if sb.exists() and sb.read_text().strip():
        branches.append(sb.read_text().strip())
    branches += [b for b in FALLBACK_BRANCHES if b not in branches]
    with tempfile.TemporaryDirectory() as tmp:
        top = None
        for b in branches:
            print(f"  downloading {b} …")
            data = download(b)
            if not data:
                continue
            sub = Path(tmp) / b.replace("/", "-")
            zipfile.ZipFile(io.BytesIO(data)).extractall(sub)
            cand = next((p for p in sub.iterdir() if p.is_dir()), None)
            if cand and (cand / "scripts" / "market_report").exists():
                top = cand
                break
            print(f"  {b} does not contain the generator; trying the next one")
        if top is None:
            print("Update failed: no downloadable copy contains the generator. Check the internet connection.")
            return 1
        for d in REPLACE_DIRS:
            src, dst = top / d, root / d
            if not src.exists():
                continue
            for item in src.rglob("*"):
                rel = item.relative_to(top)
                if str(rel).replace(os.sep, "/") in KEEP:
                    continue
                target = root / rel
                if item.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, target)
        for f in REPLACE_FILES:
            if (top / f).exists():
                (root / f).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(top / f, root / f)
        for ex in (root / "Ticker-Report.command", root / "scripts" / "run_daily.sh", root / "scripts" / "schedule_unix.sh"):
            if ex.exists():
                ex.chmod(ex.stat().st_mode | 0o755)
        unquarantine(root)
    # refresh the Python packages inside the existing environment, if there is one
    py = root / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
    if py.exists():
        print("  refreshing Python packages …")
        subprocess.call([str(py), "-m", "pip", "install", "--quiet", "-r", str(root / "scripts" / "requirements.txt")])
        subprocess.call([str(py), "-m", "playwright", "install", "chromium"], stdout=subprocess.DEVNULL)
    # rebuild the guide so it matches the new code
    try:
        sys.path.insert(0, str(root))
        from scripts.market_report.guide import write_guide  # noqa: PLC0415
        write_guide(root / "market-report")
    except Exception:  # noqa: BLE001
        pass
    print("Done. Your settings, e-mail list and reports were kept.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
