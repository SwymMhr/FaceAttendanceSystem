# truncate.ps1
# Delete ALL rows from every table, keeping the schema (ids restart at 1).
# Unlike fullwipe.ps1, this does NOT drop/recreate tables.
#
# Usage:
#   .\scripts\truncate.ps1
[CmdletBinding()]
param()

. "$PSScriptRoot\common.ps1"

Write-Host "Truncating all tables (schema kept)..." -ForegroundColor Yellow

@'
from sqlalchemy import text
from app.db.database import engine

TABLES = [
    "tbl_attendance", "tbl_periods", "tbl_period_slots",
    "tbl_embeddings", "tbl_subjects", "tbl_students",
    "tbl_batches", "tbl_users",
]
with engine.begin() as conn:
    conn.execute(text("TRUNCATE " + ", ".join(TABLES) + " RESTART IDENTITY CASCADE"))
print("All tables truncated.")
'@ | Invoke-PySnippet
