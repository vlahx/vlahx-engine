from __future__ import annotations

import os
import uvicorn

_DEFAULT_PORT = 8000


def main() -> None:
    """Pornește uvicorn cu hot-reload pe TCP (APP_PORT, implicit 8000)."""
    raw = os.environ.get("APP_PORT", "").strip()
    if raw:
        try:
            port = int(raw)
            if port <= 0:
                port = _DEFAULT_PORT
        except ValueError:
            port = _DEFAULT_PORT
    else:
        port = _DEFAULT_PORT

    # Activate hot-reload so modifications to python files & templates reload automatically without docker restart
    reload_env = os.environ.get("APP_RELOAD", "true").strip().lower()
    is_reload = reload_env in ("true", "1", "yes")

    if is_reload:
        uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True, reload_dirs=["app"])
    else:
        from main import app
        uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
