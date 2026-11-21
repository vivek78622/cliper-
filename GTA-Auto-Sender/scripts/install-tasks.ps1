# Installs two Windows scheduled tasks that run every 5 minutes, hidden, as you:
#   GtaSenderFeeder   -> clip_feeder.py  (clipper output -> queue, equal share per channel)
#   GtaSenderAutopost -> autopost.py     (queue -> Zernio -> YouTube + Instagram)
# Run once from the kit folder:  powershell -ExecutionPolicy Bypass -File scripts\install-tasks.ps1
# Dry-run inspection:            powershell -ExecutionPolicy Bypass -File scripts\install-tasks.ps1 -DryRun
# Remove them later with:        powershell -ExecutionPolicy Bypass -File scripts\install-tasks.ps1 -Remove
param(
    [switch]$Remove,
    [switch]$DryRun,
    [string]$PythonPath
)
$ErrorActionPreference = 'Stop'
$kit = (Resolve-Path (Split-Path -Parent $PSScriptRoot)).Path
$names = 'GtaSenderFeeder', 'GtaSenderAutopost'

if ($Remove) {
    foreach ($n in $names) {
        Unregister-ScheduledTask -TaskName $n -Confirm:$false -ErrorAction SilentlyContinue
    }
    Write-Host 'Tasks removed.'
    return
}

# Verify configuration and environment files exist before registering tasks
if (-not (Test-Path (Join-Path $kit 'config\channels.json'))) {
    throw 'config\channels.json is missing. Copy config\channels.example.json to config\channels.json and fill it in first.'
}
if (-not (Test-Path (Join-Path $kit '.env'))) {
    throw '.env is missing. Copy .env.example to .env and put your Zernio key in it first.'
}

# Python detection priority:
# 1. User-specified -PythonPath parameter (if provided)
# 2. Shared .venv in parent directory (..\.venv\Scripts\pythonw.exe, then python.exe)
# 3. Local .venv in GTA-Auto-Sender (.venv\Scripts\pythonw.exe, then python.exe)
# 4. PATH pythonw.exe, then python.exe
$py = $null

if ($PythonPath) {
    if (Test-Path $PythonPath) {
        $py = (Resolve-Path $PythonPath).Path
    } else {
        throw "Specified -PythonPath '$PythonPath' was not found."
    }
} else {
    $candidates = @(
        (Join-Path $kit '..\.venv\Scripts\pythonw.exe'),
        (Join-Path $kit '..\.venv\Scripts\python.exe'),
        (Join-Path $kit '.venv\Scripts\pythonw.exe'),
        (Join-Path $kit '.venv\Scripts\python.exe')
    )
    foreach ($cand in $candidates) {
        if (Test-Path $cand) {
            $py = (Resolve-Path $cand).Path
            break
        }
    }
}

if (-not $py) {
    $cmd = Get-Command pythonw.exe -ErrorAction SilentlyContinue
    if ($cmd) {
        $py = $cmd.Source
    } else {
        $cmd = Get-Command python.exe -ErrorAction SilentlyContinue
        if ($cmd) { $py = $cmd.Source }
    }
}

if (-not $py) {
    throw "No Python executable found. Please create a virtual environment or ensure Python is on PATH."
}

# Locate companion python.exe for console/pip operations (since pythonw.exe suppresses console output)
$pyDir = Split-Path -Parent $py
$pyCli = Join-Path $pyDir 'python.exe'
if (-not (Test-Path $pyCli)) {
    $pyCli = $py
}

Write-Host "Resolved Python: $py"
Write-Host "Sender directory: $kit"

# Install/verify dependencies
$reqFile = Join-Path $kit 'requirements.txt'
if (Test-Path $reqFile) {
    Write-Host "Verifying requirements with: $pyCli"
    & $pyCli -m pip install -q -r $reqFile
}

$map = @{
    'GtaSenderFeeder'   = 'clip_feeder.py'
    'GtaSenderAutopost' = 'autopost.py'
}

foreach ($n in $names) {
    $scriptFile = Join-Path $kit $map[$n]
    if (-not (Test-Path $scriptFile)) {
        throw "Target script not found: $scriptFile"
    }

    # Wrap target path in quotes to support directories containing spaces (e.g. 'clips upload')
    $argumentStr = "`"$scriptFile`""

    if ($DryRun) {
        Write-Host "[DryRun] Task '$n':"
        Write-Host "  Execute:          $py"
        Write-Host "  Argument:         $argumentStr"
        Write-Host "  WorkingDirectory: $kit"
        Write-Host "  Trigger:          Every 5 minutes (repeating)"
        continue
    }

    $action  = New-ScheduledTaskAction -Execute $py -Argument $argumentStr -WorkingDirectory $kit
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)
    $set     = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
    Register-ScheduledTask -TaskName $n -Action $action -Trigger $trigger -Settings $set -Force | Out-Null
    Write-Host "Installed $n (every 5 minutes)."
}

if ($DryRun) {
    Write-Host 'Dry run complete. No tasks were registered.'
} else {
    Write-Host 'Done. Check queue\autopost.log and queue\clip_feeder.log after about 6 minutes.'
}
