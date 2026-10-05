#!/usr/bin/env bash
# Installs the daily schedule on macOS or Linux (cron): every working day at 18:30 East Africa Time.
# Run once from the repository folder:
#
#   scripts/schedule_unix.sh                 # install (18:30 EAT, Mon–Fri)
#   scripts/schedule_unix.sh --time 18:30    # a different time of day (EAT)
#   scripts/schedule_unix.sh --with-catchup  # also run quietly at 21:00 EAT, only acts if 18:30 was preliminary
#   scripts/schedule_unix.sh --remove        # remove
#
# The time is converted from East Africa Time to this computer's time zone, so the lines in your
# crontab are in local time. macOS: the Mac must be awake at that time, and cron needs permission to
# write to the Desktop (System Settings → Privacy & Security → Full Disk Access → add /usr/sbin/cron).
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
MARK="# the-ticker-market-report"
TIME="18:30"; CATCHUP=0; REMOVE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --time) TIME="$2"; shift 2;;
    --with-catchup) CATCHUP=1; shift;;
    --remove) REMOVE=1; shift;;
    *) echo "unknown option $1"; exit 2;;
  esac
done
CUR="$(crontab -l 2>/dev/null | grep -v "$MARK" || true)"
if [ "$REMOVE" = 1 ]; then
  printf '%s\n' "$CUR" | sed '/^$/d' | crontab - ; echo "removed"; exit 0
fi
# convert HH:MM East Africa Time to local time (cron runs in the computer's own zone)
conv() { python3 - "$1" <<'PY'
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
h, m = map(int, sys.argv[1].split(":"))
eat = datetime.now(ZoneInfo("Africa/Dar_es_Salaam")).replace(hour=h, minute=m, second=0, microsecond=0)
loc = eat.astimezone()
print(f"{loc.minute} {loc.hour}")
PY
}
MAIN="$(conv "$TIME")"
LINES="${MAIN} * * 1-5 $REPO/scripts/run_daily.sh $MARK"
if [ "$CATCHUP" = 1 ]; then
  CU="$(conv 21:00)"
  LINES="$LINES
${CU} * * 1-5 $REPO/scripts/run_daily.sh $MARK"
fi
printf '%s\n%s\n' "$CUR" "$LINES" | sed '/^$/d' | crontab -
echo "installed (times shown in this computer's local time; ${TIME} East Africa Time):"
crontab -l | grep "$MARK"
echo "logs: ~/.the-ticker/run.log"
