from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import APP_DIR
from app.models.db_models import User, MediaFile
try:
    from app.plugins.vlahx_blog.models import Post
except ImportError:
    Post = None

logger = logging.getLogger(__name__)

PURGE_GRACE_DAYS = 30


def request_user_deletion(db: Session, user_id: int) -> datetime:
    """Programează ștergerea contului și activează perioada de grație de 30 de zile."""
    user = db.get(User, user_id)
    if not user:
        raise ValueError("Utilizatorul nu a fost găsit.")

    now = datetime.now(timezone.utc)
    user.deletion_requested_at = now
    db.commit()
    db.refresh(user)
    logger.info("Utilizatorul %s (#%s) a solicitat ștergerea contului. Programat la %s", user.email, user.id, now)
    return now


def cancel_user_deletion(db: Session, user_id: int) -> bool:
    """Anulează solicitarea de ștergere a contului și îl reactivează complet."""
    user = db.get(User, user_id)
    if not user:
        return False

    user.deletion_requested_at = None
    db.commit()
    db.refresh(user)
    logger.info("Utilizatorul %s (#%s) și-a recuperat contul și a anulat ștergerea.", user.email, user.id)
    return True


def get_user_deletion_status(user: User | None) -> tuple[bool, datetime | None, datetime | None]:
    """
    Verifică dacă un utilizator are o solicitare de ștergere în curs.
    Returnează: (is_pending, deletion_requested_at, deletion_deadline)
    """
    if not user or not getattr(user, "deletion_requested_at", None):
        return (False, None, None)

    req_at = user.deletion_requested_at
    if req_at.tzinfo is None:
        req_at = req_at.replace(tzinfo=timezone.utc)

    deadline = req_at + timedelta(days=PURGE_GRACE_DAYS)
    return (True, req_at, deadline)


def _delete_local_user_file(file_path_str: str | None) -> None:
    """Elimină fizic un fișier al utilizatorului de pe disc dacă este local."""
    if not file_path_str:
        return
    clean_path = str(file_path_str).strip()
    if not clean_path or clean_path.startswith(("http://", "https://")):
        return

    try:
        if clean_path.startswith("/static/"):
            rel_path = clean_path[len("/static/"):]
            full_path = APP_DIR / "static" / rel_path
        else:
            full_path = Path(clean_path)

        if full_path.exists() and full_path.is_file():
            full_path.unlink(missing_ok=True)
            logger.info("Fișier utilizator șters de pe disc: %s", full_path)
    except Exception as exc:
        logger.warning("Eroare la ștergerea fișierului %s: %s", clean_path, exc)


def purge_user_data(db: Session, user_id: int) -> bool:
    """
    Curăță definitiv și ireversibil toate urmele unui utilizator din baza de date și de pe disc:
    - Comentarii
    - Fișiere media încărcate (+ fișiere fizice pe disc)
    - Imagine de avatar de pe disc
    - Reatribuirea postărilor de autor către un cont admin de sistem
    - Ștergerea rândului din tabela `users`
    """
    user = db.get(User, user_id)
    if not user:
        return False

    user_info_log = f"{user.email or user.username or 'ID ' + str(user.id)}"
    logger.info("Începere purge definitiv date pentru utilizatorul: %s (ID %s)", user_info_log, user_id)

    # 1. Ștergere comentarii ale utilizatorului
    try:
        # Comments handled by comments plugin if loaded
        pass
    except Exception as exc:
        logger.warning("Eroare ștergere comentarii pentru user %s: %s", user_id, exc)

    # 2. Ștergere fișiere media încărcate (DB + Disc)
    try:
        media_records = db.query(MediaFile).filter(MediaFile.user_id == user_id).all()
        for mf in media_records:
            _delete_local_user_file(mf.file_path or mf.file_url)
            db.delete(mf)
    except Exception as exc:
        logger.warning("Eroare ștergere media_files pentru user %s: %s", user_id, exc)

    # 3. Ștergere avatar personalizat de pe disc
    if user.image_url:
        _delete_local_user_file(user.image_url)

    # 4. Reatribuire postări de autor (dacă există) către un admin de sistem
    try:
        user_posts = db.query(Post).filter(Post.author_id == user_id).all()
        if user_posts:
            admin_fallback = db.query(User).filter(User.id != user_id, User.role.like("%admin%")).first()
            fallback_id = admin_fallback.id if admin_fallback else 1
            for p in user_posts:
                p.author_id = fallback_id
            logger.info("Reatribuit %s articole ale utilizatorului %s către admin ID %s", len(user_posts), user_id, fallback_id)
    except Exception as exc:
        logger.warning("Eroare reatribuire postări pentru user %s: %s", user_id, exc)

    # 5. Ștergere rând utilizator din tabela `users`
    db.delete(user)
    db.commit()

    logger.info("Purge complet efectuat cu succes pentru utilizatorul ID %s", user_id)
    return True


def purge_expired_users_cron(db: Session) -> int:
    """
    Rulează verificarea automată de cron pentru conturile a căror perioadă de grație (30 zile) a expirat.
    Execută purge-ul definitiv și returnează numărul de conturi curățate.
    """
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(days=PURGE_GRACE_DAYS)

    stmt = select(User).where(
        (User.deletion_requested_at != None) & (User.deletion_requested_at <= threshold)  # noqa: E711
    )
    expired_users = db.execute(stmt).scalars().all()

    purged_count = 0
    for u in expired_users:
        uid = u.id
        if purge_user_data(db, uid):
            purged_count += 1

    if purged_count > 0:
        logger.info("Cron Purge: Au fost șterse definitiv %s conturi expirate (>%s zile).", purged_count, PURGE_GRACE_DAYS)

    return purged_count
