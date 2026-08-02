# create-student.ps1
# Create a student account via the admin API. The backend must be running.
#
# Usage:
#   .\scripts\create-student.ps1 -Email ada@example.com -Password secret `
#       -StudentCode 2024IT001 -StudentName "Ada Lovelace" -BatchId 1
[CmdletBinding()]
param(
    [string]$Email,
    [string]$Password,
    [string]$StudentCode,
    [string]$StudentName,
    [int]$BatchId
)

. "$PSScriptRoot\common.ps1"

if (-not $Email)       { $Email       = Read-Host "Email" }
if (-not $Password)    { $Password    = Read-Host "Password" -AsSecureString; $Password = [System.Net.NetworkCredential]::new('', $Password).Password }
if (-not $StudentCode) { $StudentCode = Read-Host "Student code" }
if (-not $StudentName) { $StudentName = Read-Host "Student name" }
if ($BatchId -le 0)    { $BatchId     = Read-Host "Batch id (optional, 0 for none)" }

$body = @{
    email        = $Email
    password     = $Password
    student_code = $StudentCode
    student_name = $StudentName
}
if ($BatchId -gt 0) { $body.batch_id = $BatchId }

$token = Get-AdminToken -Email $script:AdminEmail -Password $script:AdminPassword -BaseUrl $script:ApiBase
Invoke-Api -Method Post -Path "/admin/users/students" -Body $body -Token $token |
    ConvertTo-Json -Depth 5
