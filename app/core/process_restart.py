from __future__ import annotations

import os
import signal
import time


def sigterm_self_after_delay(delay_sec: float = 0.5) -> None:
    """Oprește procesul curent cu SIGTERM după un scurt delay.

    Atinge și main.py pentru a declanșa reîncărcarea automată dacă serverul rulează cu uvicorn --reload.
    Cu politica Docker ``restart: unless-stopped``, oprirea procesului principal repornește containerul.
    """
    try:
        from app.core.config import PROJECT_ROOT
        main_py = PROJECT_ROOT / "main.py"
        if main_py.exists():
            main_py.touch()
    except Exception:
        pass
    time.sleep(delay_sec)
    os.kill(os.getpid(), signal.SIGTERM)
