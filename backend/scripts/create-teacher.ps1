# create-teacher.ps1
# Create a teacher account via the admin API. The backend must be running.
#
# Usage:
#   .\scripts\create-teacher.ps1 -FullName "Jane Doe" -Email jane@example.com -Password secret
[CmdletBinding()]
param(
    [string]$FullName,
    [string]$Email,
    [string]$Password
)

. "$PSScriptRoot\common.ps1"

if (-not $FullName) { $FullName = Read-Host "Full name" }
if (-not $Email)    { $Email    = Read-Host "Email" }
if (-not $Password) { $Password = Read-Host "Password" -AsSecureString; $Password = [System.Net.NetworkCredential]::new('', $Password).Password }

$token = Get-AdminToken -Email $script:AdminEmail -Password $script:AdminPassword -BaseUrl $script:ApiBase
Invoke-Api -Method Post -Path "/admin/users/teachers" `
    -Body @{ full_name = $FullName; email = $Email; password = $Password } -Token $token |
    ConvertTo-Json -Depth 5
