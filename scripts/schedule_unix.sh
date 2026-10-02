#!/usr/bin/env bash
# Installs the schedule on macOS or Linux (cron): weekdays 16:40, 18:40, 20:40 East Africa Time
# plus 08:10 the next morning. Run once from the repository folder:
#
#   scripts/schedule_unix.sh            # install
#   scripts/schedule_unix.sh --remove   # remove
#
# cron runs in the computer's local time zone, so the lines carry CRON_TZ (supported by
# cronie/Linux and macOS 13+). If your cron ignores CRON_TZ, convert the hours yourself.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
MARK="# the-ticker-market-report"
CUR="$(crontab -l 2>/dev/null | grep -v "$MARK" || true)"
if [ "${1:-}" = "--remove" ]; then
  printf '%s\n' "$CUR" | crontab -
  echo "removed"; exit 0
fi
LINES="CRON_TZ=Africa/Dar_es_Salaam $MARK
40 16,18,20 * * 1-5 $REPO/scripts/run_daily.sh $MARK
10 8 * * 2-6 $REPO/scripts/run_daily.sh $MARK"
printf '%s\n%s\n' "$CUR" "$LINES" | sed '/^$/d' | crontab -
echo "installed:"; crontab -l | grep "$MARK"
echo "logs: ~/.the-ticker/run.log"
