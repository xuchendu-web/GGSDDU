[CmdletBinding()]
param(
  [string]$Python = "",
  [switch]$ConfigureToken,
  [switch]$Isolated,
  [switch]$Reconfigure
)
$ErrorActionPreference = 'Stop'
$skillRoot = Split-Path -Parent $PSCommandPath
$state = Join-Path $skillRoot '.iqm-runtime.json'
$runtimeEnv = Join-Path $skillRoot '.iqm-runtime.ps1'
$pypiMirror = 'https://pypi.tuna.tsinghua.edu.cn/simple'

function Test-SupportedPython([string]$Exe) {
  if (!(Test-Path -LiteralPath $Exe)) { return $false }
  try { return ((& $Exe -c 'import sys; print("%d.%d" % sys.version_info[:2])').Trim() -in @('3.11','3.12')) } catch { return $false }
}
function Save-Runtime([string]$Exe, [string]$Kind) {
  $resolved = (Resolve-Path -LiteralPath $Exe).Path
  @{ python = $resolved; kind = $Kind; configured_at = (Get-Date).ToUniversalTime().ToString('o') } |
    ConvertTo-Json | Set-Content -LiteralPath $state -Encoding utf8
  "`$env:IQM_PYTHON = '$($resolved.Replace("'", "''"))'" | Set-Content -LiteralPath $runtimeEnv -Encoding utf8
}

# Subsequent calls: reuse the explicitly saved interpreter unless the user asks
# to reconfigure it.  This avoids model-dependent Python discovery on every run.
if (!$Python -and !$Reconfigure -and (Test-Path -LiteralPath $state)) {
  try { $saved = (Get-Content -Raw -LiteralPath $state | ConvertFrom-Json).python; if (Test-SupportedPython $saved) { $Python = $saved } } catch {}
}

if (!$Python -and !$Isolated) {
  # Prefer a complete system/agent environment. preflight's recommendation is
  # deterministic and validates all runtime packages, not merely CJPY.
  $launcher = (Get-Command python -ErrorAction SilentlyContinue).Source
  if ($launcher) {
    try { $found = (& $launcher (Join-Path $skillRoot 'scripts\preflight.py') --json | ConvertFrom-Json).recommended; if ($found) { $Python = $found } } catch {}
  }
}
if (!$Python) {
  try { $candidate = (& py -3.12 -c 'import sys; print(sys.executable)' 2>$null).Trim(); if (Test-SupportedPython $candidate) { $Python=$candidate } } catch {}
  if (!$Python) { try { $candidate = (& py -3.11 -c 'import sys; print(sys.executable)' 2>$null).Trim(); if (Test-SupportedPython $candidate) { $Python=$candidate } } catch {} }
  if (!$Python) { try { $candidate = (& python -c 'import sys; print(sys.executable)' 2>$null).Trim(); if (Test-SupportedPython $candidate) { $Python=$candidate } } catch {} }
}
if (!$Python -or !(Test-SupportedPython $Python)) { throw 'Python 3.11 or 3.12 is required. Pass -Python C:\path\python.exe.' }

$kind = 'system-or-agent'
if ($Isolated) {
  $venv = Join-Path $skillRoot '.venv'
  if (!(Test-Path (Join-Path $venv 'Scripts\python.exe'))) { & $Python -m venv $venv }
  $Python = Join-Path $venv 'Scripts\python.exe'; $kind = 'skill-venv'
}

# Install only when preflight says this selected environment is incomplete.
$check = (& $Python (Join-Path $skillRoot 'scripts\preflight.py') --quick --json | ConvertFrom-Json)
if (!$check.ok) {
  & $Python -m pip install --index-url $pypiMirror -r (Join-Path $skillRoot 'requirements.txt')
  $check = (& $Python (Join-Path $skillRoot 'scripts\preflight.py') --quick --json | ConvertFrom-Json)
}
if (!$check.ok) { throw 'Environment is incomplete. Install/configure CJPY through your existing CJPY tool or provide a compatible data-source adapter, then rerun bootstrap.ps1. No CJPY wheel is bundled with this skill.' }
Save-Runtime $Python $kind
if ($ConfigureToken) { & $Python (Join-Path $skillRoot 'scripts\configure_cjpy_token.py') }
Write-Host "Ready. Saved runtime: $Python"
Write-Host "Later calls: $Python scripts\industry_monitor.py --check-env"
