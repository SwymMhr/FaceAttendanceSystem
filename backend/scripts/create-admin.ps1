# create-admin.ps1
# Bootstrap the first admin user. Idempotent: skips if the email already exists.
#
# Usage:
#   .\scripts\create-admin.ps1
#   .\scripts\create-admin.ps1 -Email me@example.com -Password secret -Name "My Name"
#
# Defaults: admin@test.com / admin123 / Test Admin
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

Write-Host "Creating admin: $Email" -ForegroundColor Yellow

@'
import sys
from app.core.security import hash_password
from app.db.database import SessionLocal
from app.models.db_models import User

email, password, name = sys.argv[1], sys.argv[2], sys.argv[3]
db = SessionLocal()
try:
    if db.query(User).filter(User.email == email).first():
        print("Admin already exists: " + email + " - skipping.")
        sys.exit(0)
    admin = User(email=email, full_name=name, role="admin",
                 password_hash=hash_password(password))
    db.add(admin)
    db.commit()
    print("Admin created: " + email + " (id=" + str(admin.id) + ", role=" + admin.role + ")")
finally:
    db.close()
'@ | Invoke-PySnippet $Email $Password $Name
