"""polaris_auth - login, sesi, dan peran untuk backend PolarisBI.

Pemakaian minimal di main.py:

    from polaris_auth import setup_auth
    setup_auth(app)          # sesudah `app = FastAPI(...)`

Untuk membatasi endpoint tertentu ke peran tertentu:

    from polaris_auth import require_role
    @app.get("/api/x", dependencies=[Depends(require_role("admin", "analyst"))])
"""
from .deps import require_admin, require_role, require_user
from .setup import setup_auth

__all__ = ["setup_auth", "require_user", "require_role", "require_admin"]
