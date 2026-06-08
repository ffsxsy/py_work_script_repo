# Replace broken CanFaultImport module in the xlsm (close Excel first).
# Run: powershell -ExecutionPolicy Bypass -File repair_vba_module.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$xlsm = Join-Path $PSScriptRoot "can_fault_recording_template.xlsm"
if (-not (Test-Path $xlsm)) {
    Write-Host "Missing: $xlsm"
    exit 1
}

python -c @"
from pathlib import Path
from build_can_fault_excel_template import build_template, _embed_vba_and_button
base = Path('.')
build_template(base / 'can_fault_recording_template.xlsx')
_embed_vba_and_button(
    base / 'can_fault_recording_template.xlsx',
    base / 'can_fault_recording_template.xlsm',
)
print('Rebuilt:', base / 'can_fault_recording_template.xlsm')
"@

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Done. Open can_fault_recording_template.xlsm and run Debug -> Compile VBAProject."
