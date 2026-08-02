# create-slot.ps1
# Create a period slot for a batch (slots are numbered automatically in order
# of creation). Times are 24-hour HH:MM. Via the admin API; backend must run.
#
# Usage:
#   .\scripts\create-slot.ps1 -BatchId 1 -StartTime "09:00" -EndTime "09:50"
[CmdletBinding()]
param(
    [int]$BatchId,
    [string]$StartTime,
    [string]$EndTime
)

. "$PSScriptRoot\common.ps1"

if ($BatchId -le 0)    { $BatchId    = Read-Host "Batch id" }
if (-not $StartTime)   { $StartTime  = Read-Host "Start time (HH:MM)" }
if (-not $EndTime)     { $EndTime    = Read-Host "End time (HH:MM)" }

$token = Get-AdminToken -Email $script:AdminEmail -Password $script:AdminPassword -BaseUrl $script:ApiBase
Invoke-Api -Method Post -Path "/admin/batches/$BatchId/period-slots" `
    -Body @{ start_time = $StartTime; end_time = $EndTime } -Token $token |
    ConvertTo-Json -Depth 5
