# clear-attendance.ps1
# Delete attendance history only (tbl_attendance). All other data is untouched.
#
# Usage:
#   .\scripts\clear-attendance.ps1
[CmdletBinding()]
param()

. "$PSScriptRoot\common.ps1"

Write-Host "Clearing attendance history..." -ForegroundColor Yellow

@'
from sqlalchemy import text
from app.db.database import engine

with engine.begin() as conn:
    conn.execute(text("TRUNCATE tbl_attendance RESTART IDENTITY CASCADE"))
print("Attendance history cleared.")
'@ | Invoke-PySnippet
