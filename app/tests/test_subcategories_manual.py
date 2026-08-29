from __future__ import annotations

import os
import sys

# Add parent directory to path to import app modules
sys.path.insert(0, str(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def test_subcategories_interactive():
    """
    Script interactiv de testare pentru funcționalitatea subcategoriilor.
    Rulează manual pentru a diagnostica problema exact.
    """

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # Configurare bază de date (folosește configurația din proiect)
    from app.core.config import DATABASE_URL

    print("=" * 60)
    print("TESTARE FUNCȚIONALITATE SUBCATEGORII")
    print("=" * 60)

    try:
        # Creare bază de date în memoria (fără a conecta la DB real)
        # Pentru testare, folosim SQLite temporar
        engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}
        )

        # Importăm modelele
        from app.models.db_models import Base

        # Creează toate tabelele
        Base.metadata.create_all(engine)

        # Creare sesiune
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        db = SessionLocal()

        # Import funcții necesare
        from app.core.posts_db import (
            create_category,
            get_category_by_slug,
            list_categories,
        )

        print("\n[1] Crearea categoriei părinte 'Tehnologie'...")
        parent = create_category(db, name="Tehnologie", parent_slug=None)
        print(f"    - ID: {parent.id}")
        print(f"    - Slug: {parent.slug}")
        print(f"    - Nume: {parent.name}")
        print(f"    - Parent ID: {parent.parent_id}")

        print("\n[2] Crearea subcategoriei 'Python'...")
        child = create_category(db, name="Python", parent_slug=parent.slug)
        print(f"    - ID: {child.id}")
        print(f"    - Slug: {child.slug}")
        print(f"    - Nume: {child.name}")
        print(f"    - Parent ID: {child.parent_id} ← TREBUIE SĂ FIE: {parent.id}")
        print(f"    - Parent este: {child.parent.name if child.parent else 'NONE'}")

        # Verificăm dacă relația funcționează corect
        print("\n[3] VERIFICARE RELATIA PĂRINTE-COPIL:")
        if child.parent_id == parent.id:
            print(f"    ✓ Corect! Subcategoria are părinte cu ID {parent.id}")
        else:
            print(
                f"    ✗ ERORÉ! Parent ID este {child.parent_id}, dar ar trebui să fie {parent.id}"
            )

        print("\n[4] Listarea tuturor categoriilor:")
        categories = list_categories(db)
        for i, cat in enumerate(categories, 1):
            path_parts = cat.name.split(" / ") if " / " in cat.name else [cat.name]
            depth = len(path_parts) - 1  # Numărul de niveluri
            print(f"    {i}. {cat.name} (depth: {depth}, slug: {cat.slug})")

        # Testăm cazul când părintele nu există
        print("\n[5] Crearea categoriei fără părinte existent:")
        try:
            orphans_cat = create_category(db, name="Orfane", parent_slug=parent.slug)
            print(f"    - Creată cu succes: {orphans_cat.name}")
            if orphans_cat.parent_id is None:
                print(f"    ✓ Corect! Nu are părinte (deoarece părintele nu există)")
            else:
                print(f"    ? Paradoxal, are părinte ID: {orphans_cat.parent_id}")
        except Exception as e:
            print(f"    ✗ Eroare: {e}")

        # Testăm cazul când subcategoria este creată cu același slug ca părintele
        print("\n[6] Crearea categoriei cu același nume ca părintele:")
        try:
            duplicate = create_category(db, name="Tehnologie", parent_slug=None)
            print(f"    - Returnează categoria existentă")
            print(f"    - ID: {duplicate.id}, Slug: {duplicate.slug}")
        except Exception as e:
            print(f"    ✗ Eroare: {e}")

        # Testăm funcția _category_full_path
        print("\n[7] Testare funcția _category_full_path:")
        from app.core.posts_db import _category_full_path

        full_path = _category_full_path(child)
        print(f"    - Calea completă pentru '{child.name}': '{full_path}'")

        # Finalizare testare
        db.close()

        print("\n" + "=" * 60)
        print("TESTARE TERMINATĂ")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"\n✗ Eroare generală: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_subcategories_interactive()

    if success:
        print("\n✓ Testarea a fost finalizată!")
        print("\n[PROVOCĂRILE DE DIAGNOSTICAT]:")
        print("  1. Subcategoria apare ca categorie normală?")
        print("  2. Relația parent_id este setată corect?")
        print("  3. Funcția list_categories afișează ierarhia?")
        input("\n[PANING] Apasă Enter pentru a continua...")
    else:
        print("\n✗ Testarea a eșuat!")
