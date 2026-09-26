"""Local backup / restore.

Backups are plain files on the user's own disk. A backup bundle is a ZIP
containing the SQLite database plus the document vault, so a landlord can
move machines or keep an offline copy on a USB stick.
"""

from __future__ import annotations

import datetime as _dt
import shutil
import zipfile
from pathlib import Path
from typing import Optional

from ..db import Database


def create_bundle(db: Database, destination: Optional[Path] = None) -> Path:
    """Zip the database + documents folder into one portable file."""
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    if destination is None:
        destination = db.backups_dir / f"landlord-backup-{stamp}.zip"
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    snapshot = db.backups_dir / f".snapshot-{stamp}.db"
    db.backup_to(snapshot)
    try:
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(snapshot, arcname="landlord.db")
            for file in sorted(db.documents_dir.rglob("*")):
                if file.is_file():
                    zf.write(file, arcname=str(Path("documents") / file.relative_to(db.documents_dir)))
            zf.writestr(
                "BACKUP-README.txt",
                "Landlord Tracker offline backup\n"
                f"Created: {_dt.datetime.now().isoformat(timespec='seconds')}\n\n"
                "This archive contains your local database and attached documents.\n"
                "It never leaves your computer unless you move it yourself.\n"
                "Restore: point the app at landlord.db, or unzip into your data folder.\n",
            )
    finally:
        snapshot.unlink(missing_ok=True)
    return destination


def restore_bundle(db: Database, bundle: Path, restore_documents: bool = True) -> Path:
    """Restore a bundle. The current database is snapshotted first (safety net)."""
    bundle = Path(bundle)
    if not bundle.exists():
        raise FileNotFoundError(bundle)

    safety = db.backup_to()
    db.close()

    with zipfile.ZipFile(bundle) as zf:
        names = zf.namelist()
        if "landlord.db" not in names:
            raise ValueError("bundle_missing_database")
        with zf.open("landlord.db") as src, open(db.path, "wb") as dst:
            shutil.copyfileobj(src, dst)
        if restore_documents:
            for name in names:
                if name.startswith("documents/") and not name.endswith("/"):
                    target = db.documents_dir / name[len("documents/"):]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(name) as src, open(target, "wb") as dst:
                        shutil.copyfileobj(src, dst)

    db.conn = __import__("sqlite3").connect(str(db.path))
    db.conn.row_factory = __import__("sqlite3").Row
    return safety


def human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} GB"


def list_bundles(db: Database) -> list[dict]:
    out = []
    for path in sorted(db.backups_dir.glob("landlord-backup-*.zip"), reverse=True):
        stat = path.stat()
        out.append(
            {
                "path": str(path),
                "name": path.name,
                "size": human_size(stat.st_size),
                "modified": _dt.datetime.fromtimestamp(stat.st_mtime)
                .isoformat(timespec="seconds"),
            }
        )
    return out


def prune_bundles(db: Database, keep: int = 10) -> int:
    paths = sorted(db.backups_dir.glob("landlord-backup-*.zip"), reverse=True)
    removed = 0
    for path in paths[keep:]:
        try:
            path.unlink()
            removed += 1
        except OSError:  # pragma: no cover
            pass
    return removed
