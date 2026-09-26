"""Settings screen: language, currency, backups, export, privacy and support.

The privacy statement lives here (and in the sidebar badge) because it is the
product promise, not fine print.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Optional

from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..context import APP_VERSION, DONATION_URL, FEATURE_EMAIL, GITHUB_REPO_URL, AppContext
from ..i18n import available_languages, tr
from ..services import backups as backup_service
from ..services import demo as demo_service
from ..services.exports import export_workbook
from ..services.imports import import_workbook
from ..services.formatting import CURRENCIES, format_path
from .widgets import card, section_title


class SettingsView(QWidget):
    def __init__(self, ctx: AppContext, parent: Optional[QWidget] = None,
                 on_language_changed=None):
        super().__init__(parent)
        self.ctx = ctx
        self.on_language_changed = on_language_changed
        self.setObjectName("Root")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        container = QWidget()
        container.setObjectName("Root")
        scroll.setWidget(container)
        self.root = QVBoxLayout(container)
        self.root.setContentsMargins(26, 22, 26, 26)
        self.root.setSpacing(16)

        self._build_header()
        self._build_privacy()
        self._build_appearance()
        self._build_data()
        self._build_sample_data()
        self._build_support()
        self._build_about()
        self.root.addStretch(1)

    # ------------------------------------------------------------------
    def _build_header(self) -> None:
        self.title = QLabel(tr("nav_settings"))
        self.title.setObjectName("PageTitle")
        self.subtitle = QLabel(tr("settings_subtitle"))
        self.subtitle.setObjectName("PageSubtitle")
        self.root.addWidget(self.title)
        self.root.addWidget(self.subtitle)

    def _build_privacy(self) -> None:
        panel = card()
        layout = panel.layout()
        self.privacy_title = section_title(tr("privacy_title"))
        self.privacy_body = QLabel(tr("privacy_body"))
        self.privacy_body.setWordWrap(True)
        self.privacy_body.setObjectName("Muted")
        badge = QLabel(tr("privacy_line"))
        badge.setObjectName("AlertChipOk")
        layout.addWidget(self.privacy_title)
        layout.addWidget(badge)
        layout.addWidget(self.privacy_body)
        self.root.addWidget(panel)

    def _build_appearance(self) -> None:
        panel = card()
        layout = panel.layout()
        layout.addWidget(section_title(tr("appearance")))

        row = QHBoxLayout()
        row.setSpacing(14)

        row.addWidget(QLabel(tr("language")))
        self.language_combo = QComboBox()
        for code, name in available_languages().items():
            self.language_combo.addItem(name, code)
        index = self.language_combo.findData(self.ctx.language)
        self.language_combo.setCurrentIndex(index if index >= 0 else 0)
        self.language_combo.currentIndexChanged.connect(self._language_changed)
        row.addWidget(self.language_combo)

        row.addSpacing(18)
        row.addWidget(QLabel(tr("currency")))
        self.currency_combo = QComboBox()
        for code in CURRENCIES:
            self.currency_combo.addItem(code, code)
        index = self.currency_combo.findData(self.ctx.currency)
        self.currency_combo.setCurrentIndex(index if index >= 0 else 0)
        self.currency_combo.currentIndexChanged.connect(self._currency_changed)
        row.addWidget(self.currency_combo)

        row.addSpacing(18)
        row.addWidget(QLabel(tr("theme")))
        self.theme_combo = QComboBox()
        self.theme_combo.addItem(tr("theme_light"), "light")
        self.theme_combo.addItem(tr("theme_dark"), "dark")
        index = self.theme_combo.findData(self.ctx.setting("theme", "light"))
        self.theme_combo.setCurrentIndex(index if index >= 0 else 0)
        self.theme_combo.currentIndexChanged.connect(self._theme_changed)
        row.addWidget(self.theme_combo)

        row.addStretch(1)
        layout.addLayout(row)
        self.root.addWidget(panel)

    def _build_data(self) -> None:
        panel = card()
        layout = panel.layout()
        layout.addWidget(section_title(tr("data_folder")))

        path_row = QHBoxLayout()
        self.path_label = QLabel(format_path(self.ctx.db.data_dir))
        self.path_label.setObjectName("Muted")
        self.path_label.setWordWrap(True)
        path_row.addWidget(self.path_label, 1)
        open_folder = QPushButton(tr("open_data_folder"))
        open_folder.clicked.connect(self._open_data_folder)
        path_row.addWidget(open_folder)
        layout.addLayout(path_row)

        layout.addWidget(section_title(tr("backup_title")))
        backup_hint = QLabel(tr("backup_body"))
        backup_hint.setObjectName("Muted")
        backup_hint.setWordWrap(True)
        layout.addWidget(backup_hint)

        backup_row = QHBoxLayout()
        backup_now = QPushButton(tr("backup_now"))
        backup_now.setObjectName("Primary")
        backup_now.clicked.connect(self._backup_now)
        backup_row.addWidget(backup_now)
        restore = QPushButton(tr("restore_backup"))
        restore.clicked.connect(self._restore_backup)
        backup_row.addWidget(restore)
        backup_row.addStretch(1)
        self.last_backup_label = QLabel(self._last_backup_text())
        self.last_backup_label.setObjectName("Muted")
        backup_row.addWidget(self.last_backup_label)
        layout.addLayout(backup_row)

        layout.addWidget(section_title(tr("export_title")))
        export_hint = QLabel(tr("export_body"))
        export_hint.setObjectName("Muted")
        export_hint.setWordWrap(True)
        layout.addWidget(export_hint)
        export_row = QHBoxLayout()
        export_button = QPushButton(tr("export_xlsx"))
        export_button.setObjectName("Primary")
        export_button.clicked.connect(self._export)
        export_row.addWidget(export_button)
        export_row.addStretch(1)
        layout.addLayout(export_row)

        self.import_title = section_title(tr("import_title"))
        layout.addWidget(self.import_title)
        self.import_hint = QLabel(tr("import_body"))
        self.import_hint.setObjectName("Muted")
        self.import_hint.setWordWrap(True)
        layout.addWidget(self.import_hint)
        import_row = QHBoxLayout()
        self.import_button = QPushButton(tr("import_xlsx"))
        self.import_button.clicked.connect(self._import)
        import_row.addWidget(self.import_button)
        import_row.addStretch(1)
        layout.addLayout(import_row)

        self.root.addWidget(panel)

    def _build_sample_data(self) -> None:
        """Let the user throw away the example data.

        The app seeds a handful of example properties on first run so the
        dashboard is not empty. Without an obvious way to clear it, a real user
        would end up mixing fake tenants in with their own.
        """
        panel = card()
        layout = panel.layout()
        self.sample_title = section_title(tr("sample_title"))
        layout.addWidget(self.sample_title)
        self.sample_hint = QLabel(tr("sample_body"))
        self.sample_hint.setObjectName("Muted")
        self.sample_hint.setWordWrap(True)
        layout.addWidget(self.sample_hint)

        row = QHBoxLayout()
        self.sample_state = QLabel("")
        self.sample_state.setObjectName("Muted")
        row.addWidget(self.sample_state, 1)
        self.remove_sample_button = QPushButton(tr("sample_remove"))
        self.remove_sample_button.setObjectName("Danger")
        self.remove_sample_button.clicked.connect(self._remove_sample)
        row.addWidget(self.remove_sample_button)
        layout.addLayout(row)

        self.root.addWidget(panel)
        self._update_sample_state()

    def _update_sample_state(self) -> None:
        loaded = demo_service.is_demo(self.ctx.db)
        self.sample_state.setText(tr("sample_loaded") if loaded else tr("sample_none"))
        self.remove_sample_button.setEnabled(loaded)

    def refresh(self) -> None:
        self._update_sample_state()
        self.last_backup_label.setText(self._last_backup_text())

    def _remove_sample(self) -> None:
        if not demo_service.is_demo(self.ctx.db):
            return
        if QMessageBox.question(self, tr("sample_title"),
                                tr("sample_confirm")) != QMessageBox.Yes:
            return
        demo_service.clear_demo(self.ctx.db)
        self._update_sample_state()
        if self.on_language_changed:
            self.on_language_changed()
        QMessageBox.information(self, tr("sample_title"), tr("sample_removed"))

    def _build_support(self) -> None:
        panel = card()
        layout = panel.layout()
        layout.addWidget(section_title(tr("support_title")))
        body = QLabel(tr("support_body"))
        body.setWordWrap(True)
        body.setObjectName("Muted")
        layout.addWidget(body)

        row = QHBoxLayout()
        donate = QPushButton(tr("support_button"))
        donate.setObjectName("Primary")
        donate.clicked.connect(lambda: self._open_url(DONATION_URL))
        row.addWidget(donate)
        row.addStretch(1)
        layout.addLayout(row)
        self.root.addWidget(panel)

    def _build_about(self) -> None:
        panel = card()
        layout = panel.layout()
        layout.addWidget(section_title(tr("nav_settings")))
        version = QLabel(tr("app_version_label", version=APP_VERSION))
        version.setObjectName("Muted")
        layout.addWidget(version)
        license_label = QLabel("GPL-3.0-or-later")
        license_label.setObjectName("Muted")
        layout.addWidget(license_label)
        row = QHBoxLayout()
        repo = QPushButton(tr("feedback_github"))
        repo.clicked.connect(lambda: self._open_url(GITHUB_REPO_URL))
        row.addWidget(repo)
        email = QLabel(FEATURE_EMAIL)
        email.setObjectName("Muted")
        row.addWidget(email)
        row.addStretch(1)
        layout.addLayout(row)
        self.root.addWidget(panel)

    # ------------------------------------------------------------------
    def _language_changed(self, _index: int) -> None:
        code = self.language_combo.currentData()
        self.ctx.set_language(code)
        self.retranslate()
        if self.on_language_changed:
            self.on_language_changed()

    def _currency_changed(self, _index: int) -> None:
        self.ctx.set_setting("currency", self.currency_combo.currentData() or "EUR")

    def _theme_changed(self, _index: int) -> None:
        self.ctx.set_theme(self.theme_combo.currentData() or "light")
        if self.on_language_changed:
            self.on_language_changed()

    def _open_data_folder(self) -> None:
        self._open_url(QUrl.fromLocalFile(str(self.ctx.db.data_dir)).toString())

    def _open_url(self, url: str) -> None:
        QDesktopServices.openUrl(QUrl(url))

    def _last_backup_text(self) -> str:
        stamp = self.ctx.setting("last_backup")
        if not stamp:
            return tr("no_data")
        return f"{tr('backup_title')}: {stamp}"

    def _backup_now(self) -> None:
        try:
            path = backup_service.create_bundle(self.ctx.db)
            backup_service.prune_bundles(self.ctx.db, keep=10)
        except OSError as error:
            QMessageBox.warning(self, tr("error"), str(error))
            return
        stamp = _dt.datetime.now().isoformat(timespec="seconds")
        self.ctx.set_setting("last_backup", stamp)
        self.last_backup_label.setText(self._last_backup_text())
        QMessageBox.information(self, tr("backup_title"), tr("backup_done", path=path))

    def _restore_backup(self) -> None:
        bundles = backup_service.list_bundles(self.ctx.db)
        if not bundles:
            path, _ = QFileDialog.getOpenFileName(
                self, tr("restore_backup"), str(self.ctx.db.backups_dir),
                "Backups (*.zip *.db);;All files (*)")
            if not path:
                return
            self._do_restore(Path(path))
            return
        labels = [f"{b['name']}  ({b['size']}, {b['modified']})" for b in bundles]
        choice, accepted = QInputDialog.getItem(
            self, tr("restore_backup"), tr("select"), labels, 0, False)
        if not accepted:
            return
        index = labels.index(choice)
        self._do_restore(Path(bundles[index]["path"]))

    def _do_restore(self, path: Path) -> None:
        if QMessageBox.question(self, tr("restore_backup"), tr("restore_confirm")) != QMessageBox.Yes:
            return
        try:
            backup_service.restore_bundle(self.ctx.db, path)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, tr("error"), str(error))
            return
        QMessageBox.information(self, tr("restore_backup"), tr("restore_done"))
        if self.on_language_changed:
            self.on_language_changed()

    def _export(self) -> None:
        if self.ctx.db.is_empty():
            QMessageBox.information(self, tr("export_title"), tr("export_empty"))
            return
        default_name = f"landlord-tracker-{_dt.date.today().isoformat()}.xlsx"
        destination, _ = QFileDialog.getSaveFileName(
            self, tr("export_xlsx"), str(Path.home() / default_name), "Excel (*.xlsx)")
        if not destination:
            return
        try:
            path = export_workbook(self.ctx.db, Path(destination), self.ctx.language)
        except Exception as error:  # surface the real reason, do not swallow it
            QMessageBox.warning(self, tr("error"), tr("export_failed", error=error))
            return
        QMessageBox.information(self, tr("export_title"), tr("export_done", path=path))
        self._open_url(QUrl.fromLocalFile(str(path.parent)).toString())

    def _import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("import_xlsx"), str(Path.home()), "Excel (*.xlsx);;All files (*)")
        if not path:
            return
        try:
            result = import_workbook(self.ctx.db, Path(path))
        except Exception as error:  # show exact row/column problems
            QMessageBox.warning(self, tr("import_title"), tr("import_failed", error=error))
            return
        if self.on_language_changed:
            self.on_language_changed()
        QMessageBox.information(
            self, tr("import_title"),
            tr("import_done", properties=result.properties, tenants=result.tenants,
               leases=result.leases, skipped=result.skipped),
        )

    # ------------------------------------------------------------------
    def retranslate(self) -> None:
        self.title.setText(tr("nav_settings"))
        self.subtitle.setText(tr("settings_subtitle"))
        self.privacy_title.setText(tr("privacy_title"))
        self.privacy_body.setText(tr("privacy_body"))
        self.theme_combo.setItemText(0, tr("theme_light"))
        self.theme_combo.setItemText(1, tr("theme_dark"))
        self.import_title.setText(tr("import_title"))
        self.import_hint.setText(tr("import_body"))
        self.import_button.setText(tr("import_xlsx"))
        self.sample_title.setText(tr("sample_title"))
        self.sample_hint.setText(tr("sample_body"))
        self.remove_sample_button.setText(tr("sample_remove"))
        self._update_sample_state()
        self.last_backup_label.setText(self._last_backup_text())
