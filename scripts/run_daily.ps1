# The Ticker · DSE Daily Market Report — local runner for Windows (PowerShell).
#
#   powershell -ExecutionPolicy Bypass -File scripts\run_daily.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\run_daily.ps1 -Force
#   powershell -ExecutionPolicy Bypass -File scripts\run_daily.ps1 -Date 2026-10-01 -Force
#
# First run creates a Python virtual environment (.venv) and downloads Chromium for the PDF.
# Settings come from scripts\.env (copy scripts\.env.example). With REPORT_PUSH=1 the new
# report is committed and pushed to GitHub so GitHub Pages publishes it; without it the
# files are only written to market-report\ on this computer.
param([string]$Date = "auto", [switch]$Force, [switch]$NoPdf)
$ErrorActionPreference = "Continue"
Set-Location (Join-Path $PSScriptRoot "..")
$logDir = Join-Path $env:USERPROFILE ".the-ticker"; New-Item -ItemType Directory -Force -Path $logDir | Out-Null
Start-Transcript -Path (Join-Path $logDir "run.log") -Append | Out-Null
Write-Host "=== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') run_daily -Date $Date -Force:$Force"

# settings
$envFile = "scripts\.env"
if (Test-Path $envFile) {
  Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$' -and $_ -notmatch '^\s*#') {
      [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2].Trim('"'), "Process")
    }
  }
}

# python environment (first run)
$py = ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
  Write-Host "first run: creating .venv and installing dependencies"
  $launcher = if (Get-Command py -ErrorAction SilentlyContinue) { "py -3" } else { "python" }
  Invoke-Expression "$launcher -m venv .venv"
  & $py -m pip install --quiet --upgrade pip
  & $py -m pip install --quiet -r scripts\requirements.txt
  & $py -m playwright install chromium
}

# Git is only needed when publishing (REPORT_PUSH=1); a ZIP download of the project works without it.
$haveGit = $false
if (Get-Command git -ErrorAction SilentlyContinue) { git rev-parse --is-inside-work-tree 2>$null | Out-Null; $haveGit = ($LASTEXITCODE -eq 0) }
$branch = $null
if ($env:REPORT_PUSH -eq "1" -and $haveGit) {
  $branch = (git rev-parse --abbrev-ref HEAD).Trim()
  git pull --rebase --autostash origin $branch
  if ($LASTEXITCODE -ne 0) { Write-Host "warning: could not pull latest $branch; continuing with the local copy" }
} elseif ($env:REPORT_PUSH -eq "1") {
  Write-Host "warning: REPORT_PUSH=1 but Git is not available here; building without publishing"
}

# build (build.py writes built=/date=/complete=/pdf= to the file named by GITHUB_OUTPUT)
$outFile = [System.IO.Path]::GetTempFileName()
$env:GITHUB_OUTPUT = $outFile
$buildArgs = @("--date", $Date); if ($Force) { $buildArgs += "--force" }; if ($NoPdf) { $buildArgs += "--no-pdf" }
& $py -m scripts.market_report.build @buildArgs
$out = @{}
Get-Content $outFile | ForEach-Object { if ($_ -match '^([a-z]+)=(.*)$') { $out[$Matches[1]] = $Matches[2] } }
Remove-Item $outFile -ErrorAction SilentlyContinue

if ($out["built"] -eq "true" -and $env:REPORT_PUSH -eq "1" -and $haveGit) {
  git add -A market-report
  git diff --cached --quiet
  if ($LASTEXITCODE -eq 0) {
    Write-Host "nothing changed to commit"
  } else {
    $name = if ($env:GIT_AUTHOR_NAME) { $env:GIT_AUTHOR_NAME } else { "the-ticker-bot" }
    $mail = if ($env:GIT_AUTHOR_EMAIL) { $env:GIT_AUTHOR_EMAIL } else { "the-ticker-bot@users.noreply.github.com" }
    git -c "user.name=$name" -c "user.email=$mail" commit -q -m "market report $($out['date']) ($($out['summary']))"
    $ok = $false
    foreach ($i in 1..3) {
      git pull --rebase origin $branch
      if ($LASTEXITCODE -eq 0) { git push origin "HEAD:$branch"; if ($LASTEXITCODE -eq 0) { $ok = $true; break } }
      git rebase --abort 2>$null
      Start-Sleep -Seconds (15 * $i)
    }
    if ($ok) { Write-Host "pushed $($out['date']) to $branch" } else { Write-Host "ERROR: could not push to $branch" }
  }
}

if ($out["built"] -eq "true" -and $out["complete"] -eq "true" -and $out["pdf"] -eq "true" -and $env:REPORT_SMTP_HOST) {
  $env:REPORT_DATE = $out["date"]
  & $py -m scripts.market_report.emailer
}
Write-Host "=== done"
Stop-Transcript | Out-Null
