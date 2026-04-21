from app.database import SqliteRepository
from app.models import Note


def test_crud_cycle(tmp_path):
    repo = SqliteRepository(tmp_path / "t.sqlite3")
    n = Note.new(user="alice")
    n.content = "hello"
    repo.insert_note(n)

    fetched = repo.get_note(n.id)
    assert fetched is not None
    assert fetched.content == "hello"
    assert fetched.version == 1

    updated = repo.update_note(
        n.id, "hello world", "#FFE066", 240, 200, "bob", expected_version=1,
    )
    assert updated is not None
    assert updated.content == "hello world"
    assert updated.version == 2
    assert updated.updated_by == "bob"

    # version mismatch
    stale = repo.update_note(
        n.id, "x", "#FFE066", 240, 200, "bob", expected_version=1,
    )
    assert stale is None

    # soft delete
    deleted = repo.soft_delete_note(n.id, "bob")
    assert deleted is not None and deleted.deleted == 1
    assert repo.list_notes() == []
    assert repo.list_notes(include_deleted=True) != []

    repo.close()
