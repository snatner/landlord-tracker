"""Feature request screen.

Privacy-preserving feedback: the app composes the message locally and then
either hands it to the user's email client, opens a GitHub issue page, or copies
it to the clipboard. Nothing is transmitted by the app itself.
"""

from __future__ import annotations

import platform
import urllib.parse
from typing import Optional

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..context import APP_VERSION, FEATURE_EMAIL, GITHUB_ISSUES_URL, AppContext
from ..i18n import tr
from .base import Field, build_widget, read_widget
from .widgets import card, section_title

CATEGORY_KEYS = [
    "feedback_cat_general",
    "feedback_cat_rent",
    "feedback_cat_tenants",
    "feedback_cat_expenses",
    "feedback_cat_renovations",
    "feedback_cat_reports",
    "feedback_cat_other",
]


class FeedbackView(QWidget):
    def __init__(self, ctx: AppContext, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.ctx = ctx
        self.setObjectName("Root")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        container = QWidget()
        container.setObjectName("Root")
        scroll.setWidget(container)
        root = QVBoxLayout(container)
        root.setContentsMargins(26, 22, 26, 26)
        root.setSpacing(16)

        self.title = QLabel(tr("feedback_title"))
        self.title.setObjectName("PageTitle")
        self.subtitle = QLabel(tr("feedback_body"))
        self.subtitle.setObjectName("PageSubtitle")
        self.subtitle.setWordWrap(True)
        root.addWidget(self.title)
        root.addWidget(self.subtitle)

        panel = card()
        layout = panel.layout()

        layout.addWidget(section_title(tr("feedback_what")))
        self.area_combo = QComboBox()
        for key in CATEGORY_KEYS:
            self.area_combo.addItem(tr(key), key)
        row = QHBoxLayout()
        row.addWidget(QLabel(tr("feedback_area")))
        row.addWidget(self.area_combo, 1)
        layout.addLayout(row)

        layout.addWidget(QLabel(tr("feedback_message")))
        self.message = QPlainTextEdit()
        self.message.setPlaceholderText(tr("feedback_placeholder"))
        self.message.setMinimumHeight(150)
        layout.addWidget(self.message)

        layout.addWidget(QLabel(tr("feedback_reply_to")))
        self.email = QLineEdit()
        self.email.setPlaceholderText(FEATURE_EMAIL)
        layout.addWidget(self.email)

        hint = QLabel(tr("feedback_privacy_note"))
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        buttons = QHBoxLayout()
        self.email_button = QPushButton(tr("feedback_send_email"))
        self.email_button.setObjectName("Primary")
        self.email_button.clicked.connect(self.send_email)
        buttons.addWidget(self.email_button)

        self.github_button = QPushButton(tr("feedback_github"))
        self.github_button.clicked.connect(self.open_github)
        buttons.addWidget(self.github_button)

        self.copy_button = QPushButton(tr("feedback_copy"))
        self.copy_button.clicked.connect(self.copy_to_clipboard)
        buttons.addWidget(self.copy_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        root.addWidget(panel)

        context_panel = card()
        cl = context_panel.layout()
        cl.addWidget(section_title(tr("feedback_context")))
        self.context_label = QLabel(self._context_text())
        self.context_label.setObjectName("Muted")
        self.context_label.setWordWrap(True)
        cl.addWidget(self.context_label)
        root.addWidget(context_panel)

        root.addStretch(1)

    # ------------------------------------------------------------------
    def _context_text(self) -> str:
        return (
            f"Landlord Tracker {APP_VERSION}\n"
            f"OS: {platform.platform()}\n"
            f"Language: {self.ctx.language} · Currency: {self.ctx.currency}\n"
            f"Properties: {self.ctx.db.count('properties')} · "
            f"Tenants: {self.ctx.db.count('tenants')} · "
            f"Leases: {self.ctx.db.count('leases')}"
        )

    def compose(self) -> tuple[str, str]:
        area = tr(self.area_combo.currentData())
        subject = f"[{tr('feedback_subject')}] {area}"
        reply = self.email.text().strip()
        lines = [
            f"=== {tr('feedback_subject')} ===",
            f"{tr('feedback_area')}: {area}",
            "",
            self.message.toPlainText().strip() or "(no details provided)",
            "",
        ]
        if reply:
            lines += [f"{tr('feedback_reply_to')}: {reply}", ""]
        lines += ["--- context ---", self._context_text()]
        return subject, "\n".join(lines)

    def _require_message(self) -> Optional[tuple[str, str]]:
        if not self.message.toPlainText().strip():
            QMessageBox.information(self, tr("feedback_title"),
                                    tr("required_field_missing",
                                       field=tr("feedback_message")))
            return None
        return self.compose()

    # -- actions --------------------------------------------------------
    def send_email(self) -> None:
        composed = self._require_message()
        if not composed:
            return
        subject, body = composed
        url = QUrl(f"mailto:{FEATURE_EMAIL}")
        from PySide6.QtCore import QUrlQuery

        query = QUrlQuery()
        query.addQueryItem("subject", subject)
        query.addQueryItem("body", body)
        url.setQuery(query)
        if QDesktopServices.openUrl(url):
            return
        self.copy_to_clipboard(message=tr("feedback_no_email"))

    def open_github(self) -> None:
        composed = self._require_message()
        if not composed:
            return
        subject, body = composed
        url = QUrl(GITHUB_ISSUES_URL)
        from PySide6.QtCore import QUrlQuery

        query = QUrlQuery()
        query.addQueryItem("title", subject)
        query.addQueryItem("body", body)
        url.setQuery(query)
        if QDesktopServices.openUrl(url):
            return
        self.copy_to_clipboard(message=tr("feedback_no_browser"))

    def copy_to_clipboard(self, message: Optional[str] = None) -> None:
        _subject, body = self.compose()
        QGuiApplication.clipboard().setText(body)
        QMessageBox.information(self, tr("feedback_title"),
                                message or tr("feedback_copied"))

    def retranslate(self) -> None:
        self.title.setText(tr("feedback_title"))
        self.subtitle.setText(tr("feedback_body"))
        self.email_button.setText(tr("feedback_send_email"))
        self.github_button.setText(tr("feedback_github"))
        self.copy_button.setText(tr("feedback_copy"))
        self.message.setPlaceholderText(tr("feedback_placeholder"))
        for index, key in enumerate(CATEGORY_KEYS):
            self.area_combo.setItemText(index, tr(key))
        self.context_label.setText(self._context_text())
