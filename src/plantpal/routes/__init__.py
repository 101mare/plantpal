"""Route modules grouped by domain. ``register_all`` mounts them on the app.

Flat per-domain routers (auth, plants, account, admin, health) keep ``main.py`` to
app wiring (lifespan, scheduler, middleware) while shared dependencies live in ``deps``.
"""

from __future__ import annotations

from fastapi import FastAPI

from . import account, admin, auth, health, plants

_ROUTERS = (auth.router, plants.router, account.router, admin.router, health.router)


def register_all(app: FastAPI) -> None:
    for router in _ROUTERS:
        app.include_router(router)
