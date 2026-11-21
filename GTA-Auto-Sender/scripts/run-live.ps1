# Keeps the GTA Auto Clipper running on ONE live stream and restarts it if it exits.
# Run one copy per stream (each in its own window). Needs the clipper folder; pass it with -Clipper.
#   powershell -ExecutionPolicy Bypass -File scripts\run-live.ps1 -Url "https://www.youtube.com/watch?v=XXXX" -Name creator1 -Clipper "C:\path\to\GTA-Auto-Clipper"
# Only start it after you looked at a real frame of the stream and saw live GTA gameplay (that is what --gameplay-confirmed promises).
# Stop:  Stop-Process -Id (Get-Content "<clipper>\work\run-live-NAME.pid")   then end any leftover ffmpeg for that stream.
param(
    [Parameter(Mandatory)][string]$Url,
    [Parameter(Mandatory)][string]$Name,
    [Parameter(Mandatory)][string]$Clipper,
    [datetime]$StopAt = (Get-Date).AddHours(24)
)
Set-Location $Clipper
New-Item -ItemType Directory -Force work | Out-Null
$PID | Set-Content "work\run-live-$Name.pid"
$n = 0
while ((Get-Date) -lt $StopAt) {
    $n++
    $log = "work\live-$Name-$n.log"
    "$(Get-Date -f 'HH:mm:ss') start clip.py $Url (log $log)" | Add-Content "work\live-$Name.runs.log"
    $p = Start-Process python -PassThru -NoNewWindow -RedirectStandardOutput $log -RedirectStandardError "$log.err" `
        -ArgumentList '-u', 'clip.py', $Url, '--gameplay-confirmed', '--max-seconds', '0', '--chunk', '60', '--top', '1',
                      '--clip-len', '28', '--lead-in', '6', '--moment-source', 'combined'
    $p.WaitForExit()
    "$(Get-Date -f 'HH:mm:ss') clip.py exited $($p.ExitCode)" | Add-Content "work\live-$Name.runs.log"
    # kill the recorder the clipper can leave behind
    Get-CimInstance Win32_Process -Filter "ParentProcessId=$($p.Id)" | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 20
}
