# create-period.ps1
# Assign a subject + teacher into a period slot for a batch (a timetable entry).
# Via the admin API; backend must be running.
#
# Day is one of: SUNDAY MONDAY TUESDAY WEDNESDAY THURSDAY FRIDAY (case-insensitive).
#
# Usage:
#   .\scripts\create-period.ps1 -BatchId 1 -SubjectId 1 -TeacherId 1 `
#       -Day MONDAY -PeriodNumber 1
[CmdletBinding()]
param(
    [int]$BatchId,
    [int]$SubjectId,
    [int]$TeacherId,
    [string]$Day,
    [int]$PeriodNumber
)

. "$PSScriptRoot\common.ps1"

if ($BatchId -le 0)      { $BatchId      = Read-Host "Batch id" }
if ($SubjectId -le 0)    { $SubjectId    = Read-Host "Subject id" }
if ($TeacherId -le 0)    { $TeacherId    = Read-Host "Teacher id" }
if (-not $Day)           { $Day          = Read-Host "Day (SUNDAY..FRIDAY)" }
if ($PeriodNumber -le 0) { $PeriodNumber = Read-Host "Period number" }

$token = Get-AdminToken -Email $script:AdminEmail -Password $script:AdminPassword -BaseUrl $script:ApiBase
Invoke-Api -Method Post -Path "/admin/periods" `
    -Body @{
        batch_id      = $BatchId
        subject_id    = $SubjectId
        teacher_id    = $TeacherId
        day_of_week   = $Day.ToUpperInvariant()
        period_number = $PeriodNumber
    } -Token $token |
    ConvertTo-Json -Depth 5
