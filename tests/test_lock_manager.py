import time

from app.sync.lock_manager import LockManager


def test_acquire_and_release():
    lm = LockManager(idle_timeout_ms=10_000)
    granted, holder = lm.acquire("n1", "alice")
    assert granted and holder == "alice"

    granted2, holder2 = lm.acquire("n1", "bob")
    assert not granted2 and holder2 == "alice"

    assert lm.release("n1", "bob") is False       # not the holder
    assert lm.release("n1", "alice") is True
    assert lm.holder("n1") is None


def test_reacquire_by_same_user():
    lm = LockManager(idle_timeout_ms=10_000)
    lm.acquire("n1", "alice")
    granted, holder = lm.acquire("n1", "alice")
    assert granted and holder == "alice"


def test_release_all_by():
    lm = LockManager(idle_timeout_ms=10_000)
    lm.acquire("n1", "alice")
    lm.acquire("n2", "alice")
    lm.acquire("n3", "bob")
    released = sorted(lm.release_all_by("alice"))
    assert released == ["n1", "n2"]
    assert lm.holder("n3") == "bob"


def test_reap_idle():
    lm = LockManager(idle_timeout_ms=10)
    lm.acquire("n1", "alice")
    time.sleep(0.05)
    stale = lm.reap_idle()
    assert stale == ["n1"]
    assert lm.holder("n1") is None
