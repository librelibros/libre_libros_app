"""Catalog refresh preserves editorial decisions and missing-book history."""
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


def test_sync_preserves_visibility_and_ownership(tmp_path, monkeypatch):
    # Import after conftest has isolated settings/modules, not during collection.
    from app.database import Base
    from app.models import Book, Organization, RepositoryProvider, RepositorySource, User, Visibility
    from app.services import bootstrap

    class SeedRepository:
        def list_files(self, prefix, branch):
            return ["books/primaria/lengua/demo/book.md"]

        def read_text(self, path, branch):
            return "# Lengua\n\nMaterial docente."

    monkeypatch.setattr(bootstrap, "repository_client_for", lambda source: SeedRepository())
    engine = create_engine(f"sqlite:///{tmp_path / 'catalog.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        teacher = User(full_name="Ana", email="ana@example.org", auth_provider="local")
        school = Organization(name="Colegio de prueba", slug="colegio-prueba")
        db.add_all([teacher, school])
        db.flush()
        source = RepositorySource(name="Prueba", slug="prueba", provider=RepositoryProvider.local)
        db.add(source)
        db.flush()
        book = Book(title="Lengua", slug="demo", course="Primaria", subject="Lengua",
                    visibility=Visibility.private, repository_source_id=source.id,
                    organization_id=school.id, owner_user_id=teacher.id, base_branch="main",
                    content_path="books/primaria/lengua/demo/book.md",
                    assets_path="books/primaria/lengua/demo/assets")
        db.add(book)
        db.commit()
        expected = (Visibility.private, teacher.id, school.id)
        bootstrap._sync_catalog_from_source(db, source)
        db.commit()
        db.expire_all()
        refreshed = db.scalars(select(Book)).one()
        assert (refreshed.visibility, refreshed.owner_user_id, refreshed.organization_id) == expected
    engine.dispose()
