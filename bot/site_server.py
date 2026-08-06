#!/usr/bin/env python3
"""
LUMENA Website — вбудований статичний сервер (aiohttp).
Railway відкриває $PORT; сайт обслуговується з bot/site_static/.
"""
import asyncio
import logging
import os
from pathlib import Path

from aiohttp import web

log = logging.getLogger("site_server")

STATIC_DIR = Path(__file__).parent / "site_static"
PORT = int(os.environ.get("PORT", 8080))


async def spa_handler(request: web.Request) -> web.Response:
    """Повертає index.html для будь-якого маршруту (SPA fallback)."""
    index = STATIC_DIR / "index.html"
    return web.FileResponse(index)


def build_app() -> web.Application:
    app = web.Application()
    # статика (CSS, JS, картинки)
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.exists():
        app.router.add_static("/assets/", assets_dir, show_index=False)
    # SPA fallback — всі маршрути → index.html
    app.router.add_get("/", spa_handler)
    app.router.add_get("/{path:.*}", spa_handler)
    return app


async def run_site() -> None:
    if not STATIC_DIR.exists():
        log.error("site_static/ не знайдено — сайт не запущено")
        return

    app = build_app()
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    log.info("✅ LUMENA website → http://0.0.0.0:%d", PORT)
    await asyncio.Event().wait()          # крутимось вічно


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="[site] %(levelname)s %(message)s",
    )
    asyncio.run(run_site())
