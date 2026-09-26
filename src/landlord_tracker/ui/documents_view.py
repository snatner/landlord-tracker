"""Documents screen: the local document vault.

Contracts, receipts, inspection reports and photos are *copied* into a folder
inside the user's data directory. Nothing is uploaded anywhere, and the
original file on disk is never moved or altered.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QMessageBox, QPushButton

from ..i18n import tr
from ..models import Document, DocumentLink
from .base import Column, CrudView, Field


class DocumentsView(CrudView):
    title_key = "nav_documents"
    subtitle_key = "documents_subtitle"
    columns = [
        Column("title", stretch=True),
        Column("related_type", 150),
        Column("related_record", 200),
        Column("file_name", 260),
        Column("created_at", 160),
    ]

    def _add_extra_controls(self, toolbar: QHBoxLayout) -> None:
        self.attach_button = QPushButton(tr("attach_file"))
        self.attach_button.clicked.connect(self.attach_file)
        toolbar.addWidget(self.attach_button)
        self.open_button = QPushButton(tr("open_file"))
        self.open_button.clicked.connect(self.open_selected)
        toolbar.addWidget(self.open_button)
        self.folder_button = QPushButton(tr("open_folder"))
        self.folder_button.clicked.connect(self.open_vault)
        toolbar.addWidget(self.folder_button)

    # -- data -----------------------------------------------------------
    def fetch(self) -> list[dict]:
        return self.ctx.db.documents()

    def _record_label(self, related_type: str, related_id: Optional[int]) -> str:
        if not related_id:
            return ""
        if related_type == DocumentLink.PROPERTY.value:
            prop = self.ctx.db.property(int(related_id))
            return prop["name"] if prop else str(related_id)
        if related_type == DocumentLink.TENANT.value:
            tenant = self.ctx.db.tenant(int(related_id))
            return tenant["full_name"] if tenant else str(related_id)
        if related_type == DocumentLink.RENOVATION.value:
            reno = self.ctx.db.renovation(int(related_id))
            return reno["title"] if reno else str(related_id)
        return str(related_id)

    def row_values(self, record: dict) -> list[Any]:
        path = record.get("file_path") or ""
        exists = Path(path).exists() if path else False
        name = Path(path).name if path else ""
        return [
            record.get("title") or "",
            tr(f"document_link_{record.get('related_type')}")
            if record.get("related_type") else "",
            self._record_label(record.get("related_type") or "", record.get("related_id")),
            (name, None if exists else "#D0534B"),
            record.get("created_at") or "",
        ]

    def _link_options(self) -> list[tuple[str, str]]:
        return [(link.value, tr(f"document_link_{link.value}")) for link in DocumentLink]

    def _target_options(self) -> list[tuple[int, str]]:
        options: list[tuple[int, str]] = [(0, tr("none"))]
        for prop in self.ctx.db.properties():
            options.append((prop["id"], prop["name"]))
        for tenant in self.ctx.db.tenants():
            options.append((tenant["id"], tenant["full_name"]))
        return options

    def form_fields(self) -> list[Field]:
        return [
            Field("title", tr("title"), required=True),
            Field("related_type", tr("related_type"), kind="combo",
                  options=self._link_options()),
            Field("related_id", tr("related_id"), kind="combo", options=self._target_options()),
            Field("notes", tr("notes"), kind="multiline"),
        ]

    def create(self, values: dict) -> None:
        self.ctx.db.add_document(Document(
            title=values.get("title") or "",
            related_type=values.get("related_type") or "",
            related_id=values.get("related_id") or None,
            notes=values.get("notes") or "",
        ))

    def update(self, record_id: int, values: dict) -> None:
        existing = self.find_record(record_id) or {}
        self.ctx.db.execute(
            "UPDATE documents SET title = ?, related_type = ?, related_id = ?, notes = ? "
            "WHERE id = ?",
            (values.get("title") or "", values.get("related_type") or "",
             values.get("related_id") or None, values.get("notes") or "", record_id),
        )
        _ = existing

    def delete(self, record_id: int) -> None:
        self.ctx.db.delete_document(record_id)

    # -- actions --------------------------------------------------------
    def attach_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("attach_file"), str(Path.home()),
            "Documents (*.pdf *.png *.jpg *.jpeg *.webp *.txt *.docx *.xlsx);;All files (*)",
        )
        if not path:
            return
        source = Path(path)
        try:
            stored = self.ctx.db.copy_document_into_vault(source)
        except OSError as error:
            QMessageBox.warning(self, tr("error"), str(error))
            return
        values = self.create_from_path(source, stored)
        self.after_change()
        _ = values

    def create_from_path(self, source: Path, stored: Path) -> int:
        return self.ctx.db.add_document(Document(
            title=source.stem,
            related_type=DocumentLink.PROPERTY.value,
            related_id=None,
            file_path=str(stored),
            notes="",
        ))

    def open_selected(self) -> None:
        record_id = self.table.selected_id()
        record = self.find_record(record_id) if record_id else None
        if not record:
            QMessageBox.information(self, tr("open_file"), tr("none_selected"))
            return
        path = Path(record.get("file_path") or "")
        if not path or not path.exists():
            QMessageBox.warning(self, tr("open_file"), tr("file_missing"))
            return
        open_path(path)

    def open_vault(self) -> None:
        open_path(self.ctx.db.documents_dir)

    def footer_text(self) -> str:
        return f"{len(self._records)} × {tr('documents')} · {tr('document_vault_hint')}"


def open_path(path: Path) -> None:
    """Open a file or folder with the desktop's default handler."""
    path = Path(path)
    try:
        if QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            return
    except Exception:  # pragma: no cover - fall back to xdg-open
        pass
    opener = "xdg-open" if sys.platform.startswith("linux") else "open"
    try:
        subprocess.Popen([opener, str(path)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:  # pragma: no cover
        pass
