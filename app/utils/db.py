from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.models.db_models import Base

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_DIR = PROJECT_ROOT / 'db'
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / 'app.db'


engine = create_engine(
    f'sqlite:///{DB_PATH}',
    connect_args={'check_same_thread': False},
    future=True,
)


@event.listens_for(engine, 'connect')
def _sqlite_pragma(dbapi_conn, _connection_record) -> None:
    cur = dbapi_conn.cursor()
    cur.execute('PRAGMA foreign_keys=ON')
    cur.execute('PRAGMA journal_mode=WAL')
    cur.execute('PRAGMA synchronous=NORMAL')

    cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session, future=True)


def init_db() -> None:
    ensure_db_permissions(DB_PATH)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        res_users = db.execute(text('PRAGMA table_info(users)'))
        user_cols = [row[1] for row in res_users.fetchall()]
        cols_to_add = [
            ('dev_status', "ALTER TABLE users ADD COLUMN dev_status VARCHAR(32) DEFAULT 'none'"),
            ('dev_notes', 'ALTER TABLE users ADD COLUMN dev_notes TEXT'),
            ('dev_requested_at', 'ALTER TABLE users ADD COLUMN dev_requested_at DATETIME'),
            ('phone', 'ALTER TABLE users ADD COLUMN phone VARCHAR(64)'),
            ('password_hash', 'ALTER TABLE users ADD COLUMN password_hash VARCHAR(256)'),
            ('email_verified', 'ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT 0'),
            ('verification_token', 'ALTER TABLE users ADD COLUMN verification_token VARCHAR(128)'),
            ('onboarding_intent', 'ALTER TABLE users ADD COLUMN onboarding_intent VARCHAR(64)'),
            ('deletion_requested_at', 'ALTER TABLE users ADD COLUMN deletion_requested_at DATETIME'),
        ]
        for col_name, sql in cols_to_add:
            if col_name not in user_cols:
                try:
                    db.execute(text(sql))
                    db.commit()
                except Exception:
                    db.rollback()

    with SessionLocal() as db:
        from app.core.i18n import get_available_locales
        from app.models.db_models import TranslationLocale as TranslationLocaleModel
        for loc in get_available_locales():
            code = loc['code']
            if not db.get(TranslationLocaleModel, code):
                db.add(TranslationLocaleModel(
                    code=code,
                    name=loc.get('name') or code.upper(),
                    enabled=bool(loc.get('enabled', True)),
                    is_default=bool(loc.get('is_default', False)),
                ))
        db.commit()



    ensure_db_permissions(DB_PATH)

def ensure_db_permissions(db_path: Path):
    try:
        if db_path.parent.exists():
            try:
                db_path.parent.chmod(0o775)
            except Exception:
                pass
            for p in db_path.parent.glob(f"{db_path.name}*"):
                try:
                    p.chmod(0o664)
                except Exception:
                    pass
    except Exception:
        pass

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
