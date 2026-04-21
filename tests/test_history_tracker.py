from app.database import SqliteRepository
from app.models import Note
from app.sync.history_tracker import HistoryTracker


def test_session_with_change_records_entry(tmp_path):
    repo = SqliteRepository(tmp_path / "h.sqlite3")
    ht = HistoryTracker(repo)
    n = Note.new(user="alice")
    n.content = "before"
    repo.insert_note(n)

    ht.begin_session(n, "alice")
    # simulate update in repo
    updated = repo.update_note(n.id, "after", n.color, n.width, n.height, "alice", 1)
    assert updated is not None

    entry = ht.end_session(updated, "alice")
    assert entry is not None
    assert entry.content_before == "before"
    assert entry.content_after == "after"


def test_session_without_change_returns_none(tmp_path):
    repo = SqliteRepository(tmp_path / "h2.sqlite3")
    ht = HistoryTracker(repo)
    n = Note.new(user="alice")
    n.content = "same"
    repo.insert_note(n)

    ht.begin_session(n, "alice")
    entry = ht.end_session(n, "alice")
    assert entry is None


def test_record_create_and_delete(tmp_path):
    repo = SqliteRepository(tmp_path / "h3.sqlite3")
    ht = HistoryTracker(repo)
    n = Note.new(user="alice")
    repo.insert_note(n)

    c = ht.record_create(n, "alice")
    d = ht.record_delete(n, "alice")
    entries = repo.list_history(n.id)
    assert len(entries) == 2
    assert {e.action for e in entries} == {"create", "delete"}
