from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from . import i18n
from .settings import AppSettings


class BackupManager(QObject):
    """호스트에서만 의미가 있다. 게스트에는 DB가 없다."""

    backupCreated = Signal(str)   # 백업 파일 경로
    backupFailed = Signal(str)    # 오류 메시지

    def __init__(self, db_path: Path, settings: AppSettings,
                 parent: QObject | None = None):
        super().__init__(parent)
        self.db_path = Path(db_path)
        self.settings = settings
        self._last_backup_ts: float = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(60 * 1000)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _target_dir(self) -> Path:
        target = self.settings.resolved_backup_dir()
        target.mkdir(parents=True, exist_ok=True)
        return target

    def _tick(self) -> None:
        if not self.settings.backup_enabled:
            return
        interval = max(60, self.settings.backup_interval_seconds())
        now = datetime.now().timestamp()
        if now - self._last_backup_ts >= interval:
            self.run_backup()

    def run_backup(self) -> Path | None:
        if not self.db_path.exists():
            self.backupFailed.emit(i18n.t("backup.err_no_db"))
            return None
        try:
            target = self._target_dir()
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = target / f"notes_{ts}.sqlite3"
            shutil.copy2(self.db_path, dest)
            self._last_backup_ts = datetime.now().timestamp()
            self._cleanup_old(target)
            self.backupCreated.emit(str(dest))
            return dest
        except OSError as e:
            self.backupFailed.emit(str(e))
            return None

    def _cleanup_old(self, target: Path) -> None:
        keep = max(1, int(self.settings.backup_keep_count))
        files = sorted(
            target.glob("notes_*.sqlite3"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old in files[keep:]:
            try:
                old.unlink()
            except OSError:
                pass

    def stop(self) -> None:
        self._timer.stop()
