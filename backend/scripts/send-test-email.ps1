# send-test-email.ps1
# Send a test absence email using the SMTP settings in backend\.env.
#
# Usage:
#   .\scripts\send-test-email.ps1
#   .\scripts\send-test-email.ps1 -To me@example.com -StudentName "Ada" -SubjectName IT -Date 2026-08-02
[CmdletBinding()]
param(
    [string]$To,
    [string]$StudentName,
    [string]$SubjectName,
    [string]$Date
)

. "$PSScriptRoot\common.ps1"

if (-not $To)         { $To         = Read-Host "Recipient email" }
if (-not $StudentName){ $StudentName = 'Test Student' }
if (-not $SubjectName){ $SubjectName = 'IT' }
if (-not $Date)       { $Date       = Get-Date -Format 'yyyy-MM-dd' }

Write-Host "Sending test absence email to $To ..." -ForegroundColor Yellow

@'
import sys
from datetime import date
from app.services.notify import send_absence_email

to, name, subject, when = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
y, m, d = (int(x) for x in when.split("-"))
send_absence_email(to, name, subject, date(y, m, d))
print("Email sent.")
'@ | Invoke-PySnippet $To $StudentName $SubjectName $Date
