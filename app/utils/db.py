from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.models.db_models import Base
from app.core.posts_fs import list_posts as list_posts_fs
from app.models.db_models import User, Post


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_DIR = PROJECT_ROOT / "db"
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "app.db"


engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
    future=True,
)


@event.listens_for(engine, "connect")
def _sqlite_pragma(dbapi_conn, _connection_record) -> None:
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA journal_mode=DELETE")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session, future=True)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        # Ensure old databases gain the new category column.
        result = db.execute(text("PRAGMA table_info(posts)"))
        columns = [row[1] for row in result.fetchall()]
        if "category" not in columns:
            try:
                db.execute(text("ALTER TABLE posts ADD COLUMN category VARCHAR(80)"))
                db.commit()
            except Exception:
                db.rollback()
        if "hero_image_url" not in columns:
            try:
                db.execute(text("ALTER TABLE posts ADD COLUMN hero_image_url VARCHAR(255)"))
                db.commit()
            except Exception:
                db.rollback()

        # Migration for users table developer application fields
        res_users = db.execute(text("PRAGMA table_info(users)"))
        user_cols = [row[1] for row in res_users.fetchall()]
        if "dev_status" not in user_cols:
            try:
                db.execute(text("ALTER TABLE users ADD COLUMN dev_status VARCHAR(32) DEFAULT 'none'"))
                db.commit()
            except Exception:
                db.rollback()
        if "dev_notes" not in user_cols:
            try:
                db.execute(text("ALTER TABLE users ADD COLUMN dev_notes TEXT"))
                db.commit()
            except Exception:
                db.rollback()

        # Migration for categories table description and translations_json fields
        res_cats = db.execute(text("PRAGMA table_info(categories)"))
        cat_cols = [row[1] for row in res_cats.fetchall()]
        if "description" not in cat_cols:
            try:
                db.execute(text("ALTER TABLE categories ADD COLUMN description TEXT DEFAULT ''"))
                db.commit()
            except Exception:
                db.rollback()
        if "translations_json" not in cat_cols:
            try:
                db.execute(text("ALTER TABLE categories ADD COLUMN translations_json TEXT DEFAULT '{}'"))
                db.commit()
            except Exception:
                db.rollback()
        if "dev_requested_at" not in user_cols:
            try:
                db.execute(text("ALTER TABLE users ADD COLUMN dev_requested_at DATETIME"))
                db.commit()
            except Exception:
                db.rollback()
        if "phone" not in user_cols:
            try:
                db.execute(text("ALTER TABLE users ADD COLUMN phone VARCHAR(64)"))
                db.commit()
            except Exception:
                db.rollback()
        if "password_hash" not in user_cols:
            try:
                db.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(256)"))
                db.commit()
            except Exception:
                db.rollback()
        if "email_verified" not in user_cols:
            try:
                db.execute(text("ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT 0"))
                db.commit()
            except Exception:
                db.rollback()
        if "verification_token" not in user_cols:
            try:
                db.execute(text("ALTER TABLE users ADD COLUMN verification_token VARCHAR(128)"))
                db.commit()
            except Exception:
                db.rollback()
        if "onboarding_intent" not in user_cols:
            try:
                db.execute(text("ALTER TABLE users ADD COLUMN onboarding_intent VARCHAR(64)"))
                db.commit()
            except Exception:
                db.rollback()
        if "deletion_requested_at" not in user_cols:
            try:
                db.execute(text("ALTER TABLE users ADD COLUMN deletion_requested_at DATETIME"))
                db.commit()
            except Exception:
                db.rollback()


    with SessionLocal() as db:
        if db.execute(
            text(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='categories' LIMIT 1"
            )
        ).scalar():
            cols = [
                row[1]
                for row in db.execute(text("PRAGMA table_info(categories)")).fetchall()
            ]
            if "parent_id" not in cols:
                try:
                    db.execute(text("ALTER TABLE categories ADD COLUMN parent_id INTEGER"))
                    db.commit()
                except Exception:
                    db.rollback()

    with SessionLocal() as db:
        from app.core.i18n import get_available_locales
        from app.models.db_models import TranslationLocale as TranslationLocaleModel
        for loc in get_available_locales():
            code = loc["code"]
            if not db.get(TranslationLocaleModel, code):
                db.add(TranslationLocaleModel(
                    code=code,
                    name=loc.get("name") or code.upper(),
                    enabled=bool(loc.get("enabled", True)),
                    is_default=bool(loc.get("is_default", False)),
                ))
        db.commit()

    # One-time seed from old JSON posts if the DB is empty.
    with SessionLocal() as db:
        posts_count = db.query(Post).count()
        if posts_count > 0:
            return

        try:
            fs_posts = list_posts_fs(include_drafts=True, base_dir=PROJECT_ROOT / "content/posts")
        except Exception:
            fs_posts = []

        if not fs_posts:
            return

        # Create a placeholder author so foreign key is satisfied.
        placeholder = db.query(User).filter(User.provider == "seed", User.oauth_id == "0").first()
        if placeholder is None:
            from datetime import datetime, timezone

            now = datetime.now(timezone.utc)
            placeholder = User(provider="seed", oauth_id="0", created_at=now)
            db.add(placeholder)
            db.commit()
            db.refresh(placeholder)

        for p in fs_posts:
            db_post = Post(
                slug=p.slug,
                author_id=placeholder.id,
                title=p.title,
                excerpt=p.excerpt,
                content_html=p.content_html,
                image_url=None,
                images_url_json=None,
                draft=bool(p.draft),
                published_at=p.published_at,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(db_post)

        db.commit()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

