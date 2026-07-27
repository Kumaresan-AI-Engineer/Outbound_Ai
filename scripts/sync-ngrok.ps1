<#
  Waits for the ngrok tunnel (started by run.bat) to come up, then:
    1. Writes the fresh public HTTPS URL into backend\.env as BASE_URL
    2. Updates the Twilio TwiML App's Voice Request URL to match

  Run BEFORE the backend starts, so the backend picks up the correct
  BASE_URL on process start (pydantic-settings only reads .env once).
#>

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root 'backend\.env'

function Read-DotEnv($path) {
    $map = @{}
    foreach ($line in Get-Content $path) {
        if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
        $idx = $line.IndexOf('=')
        $key = $line.Substring(0, $idx).Trim()
        $val = $line.Substring($idx + 1).Trim()
        $map[$key] = $val
    }
    return $map
}

# --- Wait for ngrok's local API to report a public HTTPS tunnel ---
$publicUrl = $null
for ($i = 0; $i -lt 30; $i++) {
    try {
        $resp = Invoke-RestMethod -Uri 'http://127.0.0.1:4040/api/tunnels' -TimeoutSec 2
        $https = $resp.tunnels | Where-Object { $_.proto -eq 'https' } | Select-Object -First 1
        if ($https) { $publicUrl = $https.public_url; break }
    } catch {}
    Start-Sleep -Seconds 1
}

if (-not $publicUrl) {
    Write-Host "ERROR: ngrok tunnel did not come up within 30s. Check the Ngrok window for errors." -ForegroundColor Red
    exit 1
}

Write-Host "ngrok tunnel is live: $publicUrl"

# --- Update BASE_URL in backend\.env (preserve every other line as-is) ---
$lines = Get-Content $envFile
$found = $false
$newLines = foreach ($line in $lines) {
    if ($line -match '^\s*BASE_URL\s*=') {
        $found = $true
        "BASE_URL=$publicUrl"
    } else {
        $line
    }
}
if (-not $found) { $newLines += "BASE_URL=$publicUrl" }

[System.IO.File]::WriteAllLines($envFile, $newLines, [System.Text.UTF8Encoding]::new($false))
Write-Host "backend\.env BASE_URL updated."

# --- Push the new Voice Request URL to the Twilio TwiML App ---
$cfg = Read-DotEnv $envFile
$sid = $cfg['TWILIO_ACCOUNT_SID']
$token = $cfg['TWILIO_AUTH_TOKEN']
$appSid = $cfg['TWILIO_TWIML_APP_SID']

if ($sid -and $token -and $appSid -and $sid -ne 'your_twilio_account_sid') {
    $voiceUrl = "$publicUrl/calls/twiml-app"
    $pair = "${sid}:${token}"
    $b64 = [System.Convert]::ToBase64String([System.Text.Encoding]::ASCII.GetBytes($pair))
    $headers = @{ Authorization = "Basic $b64" }
    $uri = "https://api.twilio.com/2010-04-01/Accounts/$sid/Applications/$appSid.json"

    try {
        Invoke-RestMethod -Uri $uri -Method Post -Headers $headers -Body @{ VoiceUrl = $voiceUrl } | Out-Null
        Write-Host "Twilio TwiML App Voice Request URL updated to: $voiceUrl"
    } catch {
        Write-Host "WARNING: Failed to update Twilio TwiML App automatically: $($_.Exception.Message)" -ForegroundColor Yellow
        Write-Host "Set it manually in the Twilio Console -> Voice -> TwiML Apps -> Voice Request URL:" -ForegroundColor Yellow
        Write-Host "  $voiceUrl" -ForegroundColor Yellow
    }
} else {
    Write-Host "WARNING: Twilio credentials not fully set in backend\.env - skipped auto-updating the TwiML App." -ForegroundColor Yellow
}

exit 0
