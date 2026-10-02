#!/usr/bin/env bash
# The Ticker · DSE Daily Market Report — local runner for macOS / Linux.
#
#   scripts/run_daily.sh                 build the last trading day if not built yet
#   scripts/run_daily.sh --force         rebuild it
#   scripts/run_daily.sh --date 2026-10-01 --force
#
# First run creates a Python virtual environment (.venv) and downloads Chromium for the PDF.
# Settings come from scripts/.env (copy scripts/.env.example). With REPORT_PUSH=1 the new
# report is committed and pushed to GitHub so GitHub Pages publishes it; without it the
# files are only written to market-report/ on this computer.
set -euo pipefail
cd "$(dirname "$0")/.."
LOGDIR="${HOME}/.the-ticker"; mkdir -p "$LOGDIR"
exec > >(tee -a "$LOGDIR/run.log") 2>&1
echo "=== $(date '+%Y-%m-%d %H:%M:%S %Z') run_daily $*"

if [ -f scripts/.env ]; then set -a; . scripts/.env; set +a; fi

PY=.venv/bin/python
if [ ! -x "$PY" ]; then
  echo "first run: creating .venv and installing dependencies"
  python3 -m venv .venv
  "$PY" -m pip install --quiet --upgrade pip
  "$PY" -m pip install --quiet -r scripts/requirements.txt
  "$PY" -m playwright install chromium
fi

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [ "${REPORT_PUSH:-0}" = "1" ]; then
  git pull --rebase --autostash origin "$BRANCH" || echo "warning: could not pull latest $BRANCH; continuing with the local copy"
fi

OUT="$(mktemp)"; export GITHUB_OUTPUT="$OUT"   # build.py writes built=/date=/complete=/pdf= here
"$PY" -m scripts.market_report.build "$@" || echo "build exited with status $?"
BUILT="$(grep -m1 '^built=' "$OUT" | cut -d= -f2 || true)"
DATE="$(grep -m1 '^date=' "$OUT" | cut -d= -f2 || true)"
COMPLETE="$(grep -m1 '^complete=' "$OUT" | cut -d= -f2 || true)"
PDF="$(grep -m1 '^pdf=' "$OUT" | cut -d= -f2 || true)"
SUMMARY="$(grep -m1 '^summary=' "$OUT" | cut -d= -f2- || true)"
rm -f "$OUT"

if [ "$BUILT" = "true" ] && [ "${REPORT_PUSH:-0}" = "1" ]; then
  git add -A market-report
  if git diff --cached --quiet; then
    echo "nothing changed to commit"
  else
    git -c user.name="${GIT_AUTHOR_NAME:-the-ticker-bot}" -c user.email="${GIT_AUTHOR_EMAIL:-the-ticker-bot@users.noreply.github.com}" \
      commit -q -m "market report ${DATE} (${SUMMARY})"
    ok=0
    for i in 1 2 3; do
      if git pull --rebase origin "$BRANCH" && git push origin "HEAD:$BRANCH"; then ok=1; break; fi
      git rebase --abort 2>/dev/null || true
      sleep $((i * 15))
    done
    [ "$ok" = 1 ] && echo "pushed ${DATE} to ${BRANCH}" || echo "ERROR: could not push to ${BRANCH}"
  fi
fi

if [ "$BUILT" = "true" ] && [ "$COMPLETE" = "true" ] && [ "$PDF" = "true" ] && [ -n "${REPORT_SMTP_HOST:-}" ]; then
  REPORT_DATE="$DATE" "$PY" -m scripts.market_report.emailer || echo "warning: e-mail failed"
fi
echo "=== done"
