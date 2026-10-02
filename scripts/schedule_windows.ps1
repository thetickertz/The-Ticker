# Registers Windows Task Scheduler jobs that run scripts\run_daily.ps1 at 16:40, 18:40 and 20:40
# East Africa Time plus 08:10 the next morning, every weekday. Run once, from the repository folder,
# in an elevated or normal PowerShell:
#
#   powershell -ExecutionPolicy Bypass -File scripts\schedule_windows.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\schedule_windows.ps1 -Remove
#
# The task runs whether or not you are logged in only if you tick "Run whether user is logged on or
# not" in Task Scheduler and enter your password; by default it runs when you are logged in and
# catches up as soon as the computer is on if a start was missed.
param([switch]$Remove)
$taskName = "The Ticker - DSE Daily Market Report"
if ($Remove) { Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue; Write-Host "removed $taskName"; exit 0 }

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$script = Join-Path $repo "scripts\run_daily.ps1"
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`"" -WorkingDirectory $repo

# Times are converted from East Africa Time (UTC+3) to this computer's time zone.
$eat = [System.TimeZoneInfo]::FindSystemTimeZoneById("E. Africa Standard Time")
$local = [System.TimeZoneInfo]::Local
function LocalTime([string]$hhmm) {
  $t = [datetime]::ParseExact("2026-01-05 $hhmm", "yyyy-MM-dd HH:mm", $null)   # a Monday
  $utc = [System.TimeZoneInfo]::ConvertTimeToUtc($t, $eat)
  return [System.TimeZoneInfo]::ConvertTimeFromUtc($utc, $local)
}
$days = "Monday","Tuesday","Wednesday","Thursday","Friday"
$triggers = @()
foreach ($hhmm in "16:40","18:40","20:40") { $triggers += New-ScheduledTaskTrigger -Weekly -DaysOfWeek $days -At (LocalTime $hhmm) }
$triggers += New-ScheduledTaskTrigger -Weekly -DaysOfWeek "Tuesday","Wednesday","Thursday","Friday","Saturday" -At (LocalTime "08:10")

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $triggers -Settings $settings -Force | Out-Null
Write-Host "registered '$taskName' with $($triggers.Count) triggers (local times):"
$triggers | ForEach-Object { Write-Host ("  " + $_.StartBoundary) }
Write-Host "run it now with:  schtasks /Run /TN `"$taskName`""
