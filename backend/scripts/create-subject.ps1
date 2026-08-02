# create-subject.ps1
# Create a subject via the admin API. The backend must be running (see API_BASE).
#
# Usage:
#   .\scripts\create-subject.ps1 -SubjectCode IT -SubjectName "Information Technology"
[CmdletBinding()]
param(
    [string]$SubjectCode,
    [string]$SubjectName
)

. "$PSScriptRoot\common.ps1"

if (-not $SubjectCode) { $SubjectCode = Read-Host "Subject code" }
if (-not $SubjectName) { $SubjectName = Read-Host "Subject name" }

$token = Get-AdminToken -Email $script:AdminEmail -Password $script:AdminPassword -BaseUrl $script:ApiBase
Invoke-Api -Method Post -Path "/admin/subjects" `
    -Body @{ subject_code = $SubjectCode; subject_name = $SubjectName } -Token $token |
    ConvertTo-Json -Depth 5
