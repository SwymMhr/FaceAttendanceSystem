# common.ps1
# Shared setup + helpers for the backend admin/maintenance scripts.
# Every script in this folder starts with:  . "$PSScriptRoot\common.ps1"
#
# What this does:
#   * chdirs to backend\ so `app.*` imports and backend\.env resolve correctly,
#     no matter where the script was invoked from.
#   * Resolves the Python interpreter (override with $env:PYTHON).
#   * Defaults for the admin API login (override with $env:ADMIN_EMAIL,
#     $env:ADMIN_PASSWORD, $env:API_BASE).
#   * Helper functions: Get-AdminToken, Invoke-Api.

[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:BackendDir = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $script:BackendDir

$script:PythonExe = if ($env:PYTHON) { $env:PYTHON } else { 'python' }
$script:AdminEmail   = if ($env:ADMIN_EMAIL)   { $env:ADMIN_EMAIL }   else { 'admin@test.com' }
$script:AdminPassword = if ($env:ADMIN_PASSWORD) { $env:ADMIN_PASSWORD } else { 'admin123' }
$script:ApiBase = if ($env:API_BASE) { $env:API_BASE } else { 'http://127.0.0.1:8000' }

# Log in as the admin user and return the bearer token.
function Get-AdminToken {
    param(
        [string]$Email,
        [string]$Password,
        [string]$BaseUrl
    )
    $body = @{ email = $Email; password = $Password } | ConvertTo-Json
    $resp = Invoke-RestMethod -Method Post -Uri "$BaseUrl/login" `
        -ContentType 'application/json' -Body $body
    if (-not $resp.access_token) {
        throw "Login failed for '$Email'. Response: $($resp | ConvertTo-Json -Compress)"
    }
    return $resp.access_token
}

# Call a backend API endpoint as the admin user.
function Invoke-Api {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Method,
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [object]$Body,
        [string]$Token
    )
    $headers = @{}
    if ($Token) { $headers.Authorization = "Bearer $Token" }

    $params = @{
        Method  = $Method
        Uri     = "$script:ApiBase$Path"
        Headers = $headers
    }
    if ($null -ne $Body) {
        $params.ContentType = 'application/json'
        $params.Body = ($Body | ConvertTo-Json -Compress -Depth 5)
    }
    return Invoke-RestMethod @params
}

# Run a python snippet from stdin, forwarding positional args to python
# (via $args — in PS 5.1 a [string[]] param only binds the first positional
# arg, so we use the automatic $args variable instead).
function Invoke-PySnippet {
    $code = ($input | Out-String)
    $code | & $script:PythonExe - @args
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
