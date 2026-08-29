from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    oauth_id: Mapped[str] = mapped_column(String(128), nullable=False)

    username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(256), nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    verification_token: Mapped[str | None] = mapped_column(String(128), nullable=True)
    onboarding_intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str] = mapped_column(String(64), nullable=False, default="reader")
    dev_status: Mapped[str | None] = mapped_column(String(32), nullable=True, default="none")
    dev_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    dev_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deletion_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    @property
    def roles_list(self) -> list[str]:
        if not self.role:
            return ["reader"]
        return [r.strip().lower() for r in self.role.split(",") if r.strip()]

    def has_role(self, *allowed_roles: str) -> bool:
        user_roles = set(self.roles_list)
        if "admin" in user_roles:
            return True
        return bool(user_roles.intersection(set(allowed_roles)))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    posts: Mapped[list["Post"]] = relationship(back_populates="author")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True, default="")
    translations_json: Mapped[str | None] = mapped_column(Text, nullable=True, default="{}")
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)

    parent: Mapped[Optional["Category"]] = relationship(
        back_populates="children",
        remote_side=[id],
        foreign_keys=[parent_id],
    )
    children: Mapped[list["Category"]] = relationship(back_populates="parent", cascade="all, delete-orphan")


class AppSetting(Base):
    """
    Setări cheie-valoare pentru pluginuri / integrări (Telegram notificări, SMTP newsletter).
    """

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")


class TranslationLocale(Base):
    """Limbi disponibile pentru site și traduceri."""

    __tablename__ = "translation_locales"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class TranslationEntry(Base):
    """Traduceri key/value salvate în DB."""

    __tablename__ = "translation_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    locale_code: Mapped[str] = mapped_column(ForeignKey("translation_locales.code"), nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")

    __table_args__ = {"sqlite_autoincrement": True}


class Plugin(Base):
    """
    Informații despre plugin-urile instalate și starea lor.
    """

    __tablename__ = "plugins"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # plugin slug
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(String(128), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    installed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    settings: Mapped[list["PluginSetting"]] = relationship(
        back_populates="plugin", cascade="all, delete-orphan"
    )


class PluginSetting(Base):
    """
    Setări specifice pentru fiecare plugin (cheie-valoare).
    """

    __tablename__ = "plugin_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plugin_id: Mapped[str] = mapped_column(ForeignKey("plugins.id"), nullable=False)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    plugin: Mapped["Plugin"] = relationship(back_populates="settings")


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)

    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    title: Mapped[str] = mapped_column(String(220), nullable=False)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    content_html: Mapped[str] = mapped_column(Text, nullable=False)

    hero_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)  # pentru og_image, fallback la hero
    images_url_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list/dict
    meta_keywords: Mapped[str | None] = mapped_column(Text, nullable=True)

    draft: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    author: Mapped["User"] = relationship(back_populates="posts")
    translations: Mapped[list["PostTranslation"]] = relationship(back_populates="post", cascade="all, delete-orphan")



class PostTranslation(Base):

    __tablename__ = "post_translations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    locale_code: Mapped[str] = mapped_column(ForeignKey("translation_locales.code"), nullable=False)

    title: Mapped[str] = mapped_column(String(220), nullable=False)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_html: Mapped[str] = mapped_column(Text, nullable=False, default="")
    meta_keywords: Mapped[str | None] = mapped_column(Text, nullable=True)

    post: Mapped["Post"] = relationship(back_populates="translations")


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_slug: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("comments.id", ondelete="CASCADE"), nullable=True, default=None)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    user_name: Mapped[str] = mapped_column(String(128), nullable=False)
    user_avatar: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="approved", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped["User"] = relationship()


class MediaFile(Base):
    __tablename__ = "media_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_url: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    alt_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="general", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped["User"] = relationship()
