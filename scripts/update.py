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
KEEP = {"scripts/.env", "scripts/recipients.txt"}
REPLACE_DIRS = ["scripts"]
REPLACE_FILES = ["Ticker-Report.bat", "Ticker-Report.command", "market-report/README.md"]


def project_root() -> Path:
    here = Path(__file__).resolve().parent.parent if "__file__" in globals() and Path(__file__).exists() else Path.cwd()
    for cand in (here, Path.cwd()):
        if (cand / "scripts" / "market_report").exists() or (cand / "scripts").exists():
            return cand
    return Path.cwd()


def download(branch: str) -> bytes | None:
    url = f"https://github.com/{REPO}/archive/refs/heads/{branch}.zip"
    try:
        with urllib.request.urlopen(url, timeout=120) as r:
            return r.read()
    except Exception as e:  # noqa: BLE001
        print(f"  could not download {branch}: {e}")
        return None


def main() -> int:
    root = project_root()
    print(f"Updating the generator in {root}")
    branches = []
    sb = root / "scripts" / "SOURCE_BRANCH"
    if sb.exists() and sb.read_text().strip():
        branches.append(sb.read_text().strip())
    if "main" not in branches:
        branches.append("main")
    data = None
    for b in branches:
        print(f"  downloading {b} …")
        data = download(b)
        if data:
            break
    if not data:
        print("Update failed: nothing could be downloaded. Check the internet connection.")
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        zf = zipfile.ZipFile(io.BytesIO(data))
        zf.extractall(tmp)
        top = next(p for p in Path(tmp).iterdir() if p.is_dir())
        if not (top / "scripts" / "market_report").exists():
            print("Update failed: the downloaded copy does not contain the generator (is the branch right?)")
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
