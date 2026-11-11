# Registers a Windows Task Scheduler job that runs scripts\run_daily.ps1 every working day at
# 18:30 East Africa Time (converted to this computer's time zone). Run once from the repository folder:
#
#   powershell -ExecutionPolicy Bypass -File scripts\schedule_windows.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\schedule_windows.ps1 -Time 18:30
#   powershell -ExecutionPolicy Bypass -File scripts\schedule_windows.ps1 -WithCatchup   # also 21:00 EAT, only acts if needed
#   powershell -ExecutionPolicy Bypass -File scripts\schedule_windows.ps1 -Remove
#
# By default the task runs when you are logged in, wakes the PC if asleep, and catches up as soon as
# the computer is on if a start was missed. To run while logged out, open Task Scheduler, edit the
# task and tick "Run whether user is logged on or not".
param([string]$Time = "18:30", [switch]$WithCatchup, [switch]$Remove)
$taskName = "The Ticker - DSE Daily Market Report"
if ($Remove) { Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue; Write-Host "removed $taskName"; exit 0 }

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$script = Join-Path $repo "scripts\run_daily.ps1"
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`"" -WorkingDirectory $repo

$eat = [System.TimeZoneInfo]::FindSystemTimeZoneById("E. Africa Standard Time")
$local = [System.TimeZoneInfo]::Local
function LocalTime([string]$hhmm) {
  $t = [datetime]::ParseExact("2026-01-05 $hhmm", "yyyy-MM-dd HH:mm", $null)   # a Monday
  $utc = [System.TimeZoneInfo]::ConvertTimeToUtc($t, $eat)
  return [System.TimeZoneInfo]::ConvertTimeFromUtc($utc, $local)
}
$days = "Monday","Tuesday","Wednesday","Thursday","Friday"
$triggers = @(New-ScheduledTaskTrigger -Weekly -DaysOfWeek $days -At (LocalTime $Time))
if ($WithCatchup) { $triggers += New-ScheduledTaskTrigger -Weekly -DaysOfWeek $days -At (LocalTime "21:00") }

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $triggers -Settings $settings -Force | Out-Null
Write-Host "registered '$taskName' ($Time East Africa Time, Monday to Friday) — local start times:"
$triggers | ForEach-Object { Write-Host ("  " + $_.StartBoundary) }
Write-Host "run it now with:  schtasks /Run /TN `"$taskName`""
