# fresh-start.ps1
# One-shot reset: wipe the DB, recreate the schema, and create a fresh admin.
# All data is lost. Then start the backend and create your batches/subjects.
#
# Usage:
#   .\scripts\fresh-start.ps1
#   .\scripts\fresh-start.ps1 -Email admin@test.com -Password admin123 -Name "Test Admin"
[CmdletBinding()]
param(
    [string]$Email,
    [string]$Password,
    [string]$Name
)

. "$PSScriptRoot\common.ps1"

if (-not $Email)    { $Email    = $script:AdminEmail }
if (-not $Password) { $Password = $script:AdminPassword }
if (-not $Name)     { $Name     = 'Test Admin' }

Write-Host ">>> Rebuilding the database schema..." -ForegroundColor Yellow
@'
from app.db.database import engine, Base
import app.models.db_models

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
print("Schema rebuilt.")
'@ | Invoke-PySnippet

Write-Host ">>> Creating admin $Email ..." -ForegroundColor Yellow
@'
import sys
from app.core.security import hash_password
from app.db.database import SessionLocal
from app.models.db_models import User

email, password, name = sys.argv[1], sys.argv[2], sys.argv[3]
db = SessionLocal()
try:
    user = User(email=email, full_name=name, role="admin",
                password_hash=hash_password(password))
    db.add(user)
    db.commit()
    print("Admin created: " + email)
finally:
    db.close()
'@ | Invoke-PySnippet $Email $Password $Name

Write-Host ""
Write-Host "Done. Start the backend, then create a batch with:" -ForegroundColor Green
Write-Host "  .\scripts\create-batch.ps1 -BatchName '2024 Software'"
