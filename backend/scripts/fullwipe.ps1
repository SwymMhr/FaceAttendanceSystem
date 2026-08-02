# fullwipe.ps1
# Drop and recreate the entire database schema. ALL DATA IS LOST.
#
# Usage:
#   .\scripts\fullwipe.ps1
#
# Requires PostgreSQL to be running (see DATABASE_URL in backend\.env).
[CmdletBinding()]
param()

. "$PSScriptRoot\common.ps1"

Write-Host "Dropping and recreating database schema..." -ForegroundColor Yellow

@'
from app.db.database import engine, Base
import app.models.db_models

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

print("Schema rebuilt successfully.")
'@ | Invoke-PySnippet

@'
from sqlalchemy import inspect
from app.db.database import engine

insp = inspect(engine)
print("Tables: " + ", ".join(sorted(insp.get_table_names())))
'@ | Invoke-PySnippet
