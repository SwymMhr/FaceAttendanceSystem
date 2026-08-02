# run-tests.ps1
# Run the backend smoke tests.
#
# Usage:
#   .\scripts\run-tests.ps1
[CmdletBinding()]
param()

. "$PSScriptRoot\common.ps1"

$tests = @('test_db.py', 'test_cctv_service.py', 'test_model.py')

foreach ($t in $tests) {
    Write-Host "== $t ==" -ForegroundColor Yellow
    & $script:PythonExe $t
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "$t FAILED"
        exit $LASTEXITCODE
    }
}
Write-Host "All tests passed." -ForegroundColor Green
