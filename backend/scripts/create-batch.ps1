# create-batch.ps1
# Create a batch via the admin API. The backend must be running (see API_BASE).
#
# Usage:
#   .\scripts\create-batch.ps1 -BatchName "2024 Software"
[CmdletBinding()]
param(
    [string]$BatchName
)

. "$PSScriptRoot\common.ps1"

if (-not $BatchName) { $BatchName = Read-Host "Batch name" }

$token = Get-AdminToken -Email $script:AdminEmail -Password $script:AdminPassword -BaseUrl $script:ApiBase
Invoke-Api -Method Post -Path "/admin/batches" -Body @{ batch_name = $BatchName } -Token $token |
    ConvertTo-Json -Depth 5
