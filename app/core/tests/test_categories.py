from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.posts_db import (
    create_category,
    get_category_by_slug,
    list_categories,
)


class TestSubcategories:
    """Testări pentru funcționalitatea subcategoriilor."""

    def test_create_parent_and_child(self, db):
        """Creare categorie părinte și subcategorie."""
        # Creăm o categorie părinte
        parent = create_category(db, name="Tehnologie", parent_slug=None)

        # Creăm o subcategorie
        child = create_category(db, name="Python", parent_slug=parent.slug)

        # Verificăm că subcategoria are părinte corect
        assert child.parent_id == parent.id
        # Admin UI trimite ID-ul părintelui, nu slug-ul
        child_by_id = create_category(db, name="Django", parent_slug=str(parent.id))
        assert child_by_id.parent_id == parent.id
        assert child.parent is not None
        assert child.parent.name == "Tehnologie"

    def test_create_category_without_parent(self, db):
        """Creare categorie fără părinte."""
        category = create_category(db, name="Automobile", parent_slug=None)

        assert category.parent_id is None
        assert category.parent is None

    def test_list_categories_with_subcategories(self, db):
        """Listarea categoriilor cu subcategorii trebuie să includă ierarhia."""
        # Creăm structură de ierarhie
        parent = create_category(db, name="Automotive", parent_slug=None)

        child1 = create_category(db, name="Camioane", parent_slug=parent.slug)

        child2 = create_category(db, name="Autobuze", parent_slug=parent.slug)

        # Listăm categoriile - toate subcategoriile trebuie să fie în listă
        categories = list_categories(db)

        # Verificăm că toate categoriile apar în listă
        category_names = [cat.name for cat in categories]
        assert "Automotive" in category_names
        assert "Camioane" in category_names
        assert "Autobuze" in category_names

    def test_create_category_with_existing_slug(self, db):
        """Testăm că nu putem crea categorie cu slug duplicat."""
        # Creăm prima categorie
        cat1 = create_category(db, name="Tehnologie", parent_slug=None)

        # Încercăm să creăm categoria cu același nume - trebuie să returneze cea existentă
        cat2 = create_category(db, name="Tehnologie", parent_slug=None)

        assert cat1.slug == cat2.slug
        assert cat1.id == cat2.id

    def test_nested_subcategories(self, db):
        """Testăm subcategorii anidate (nivel 1 -> nivel 2 -> nivel 3)."""
        # Nivel 0: Radacina principală
        level0 = create_category(db, name="Toate", parent_slug=None)

        # Nivel 1
        level1 = create_category(db, name="Dinamic", parent_slug=level0.slug)

        # Nivel 2
        level2 = create_category(db, name="Circuitoare", parent_slug=level1.slug)

        # Verificăm ierarhia completă
        assert level1.parent_id == level0.id
        assert level2.parent_id == level1.id

        # Testăm că _category_full_path returnează calea corectă
        from app.core.posts_db import _category_full_path

        full_path = _category_full_path(level2)
        assert "Toate / Dinamic / Circuitoare" in full_path

    def test_category_depth_in_list(self, db):
        """Verificăm atributul depth în list_categories."""
        parent = create_category(db, name="Categorie", parent_slug=None)
        child = create_category(db, name="Subcategorie", parent_slug=parent.slug)

        categories = list_categories(db)

        # Categoriile fără părinte au depth=0
        root_cats = [cat for cat in categories if cat.depth == 0]
        assert any(cat.name == "Categorie" for cat in root_cats)

        # Subcategoriile au depth>=1
        child_cats = [cat for cat in categories if cat.depth >= 1]
        assert any(cat.name == "Subcategorie" for cat in child_cats)
