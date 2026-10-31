from __future__ import annotations

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from . import service
from .middleware import AuthMiddleware
from .router import router


def setup_auth(app: FastAPI) -> None:
    """Pasang login ke aplikasi FastAPI: buat tabel, daftarkan /auth/*, dan jaga semua /api/*.

    Boleh dipanggil sebelum maupun sesudah CORSMiddleware dipasang; fungsi ini memastikan
    CORS tetap berada paling luar supaya respons 401 tetap membawa header CORS.
    """
    service.init_auth()
    app.include_router(router)
    app.add_middleware(AuthMiddleware)
    # CORS harus paling luar (indeks 0 = paling luar di Starlette)
    cors = [m for m in app.user_middleware if m.cls is CORSMiddleware]
    if cors:
        for m in cors:
            app.user_middleware.remove(m)
        for m in reversed(cors):
            app.user_middleware.insert(0, m)
