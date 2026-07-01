# One-time helper: allow Excel VBA access for this user, then build .xlsm with Import button.
# Output targets Excel 2016 / 2019 / 2021 / Microsoft 365 (Windows).
# Run: powershell -ExecutionPolicy Bypass -File setup_and_build_excel_template.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

foreach ($ver in @("16.0", "15.0", "14.0")) {
    $key = "HKCU:\Software\Microsoft\Office\$ver\Excel\Security"
    if (Test-Path $key) {
        New-ItemProperty -Path $key -Name "AccessVBOM" -Value 1 -PropertyType DWord -Force | Out-Null
        Write-Host "Set AccessVBOM=1 for Office $ver Excel"
    }
}

python build_can_fault_excel_template.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (Test-Path ".\can_fault_recording_template.xlsm") {
    Write-Host ""
    Write-Host "Done. Open: can_fault_recording_template.xlsm"
    Write-Host "Click [Import CSV...] on Instructions sheet (enable macros)."
}
