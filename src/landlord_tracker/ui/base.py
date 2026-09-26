"""Shared view infrastructure: CRUD page scaffold, form dialogs, table helpers.

Six of the app's screens are the same shape (list + add/edit/delete + search),
so the behaviour lives here once and each view only declares its columns,
its data source and its form fields.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Sequence

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..context import AppContext
from ..i18n import tr
from ..services.formatting import format_money
from .widgets import EmptyState, hline, subtitle

EMPTY_DATE = QDate(1900, 1, 1)


# --------------------------------------------------------------------------
# form field specification
# --------------------------------------------------------------------------
@dataclass
class Field:
    """Declarative form field.

    ``kind`` is one of: text, money, int, float, date, combo, multiline, check,
    password. ``options`` for combos is a list of ``(value, label)`` pairs —
    values are stored canonically, labels are translated.
    """

    name: str
    label: str
    kind: str = "text"
    required: bool = False
    options: list[tuple[str, str]] = field(default_factory=list)
    default: Any = None
    placeholder: str = ""
    minimum: float = 0.0
    maximum: float = 100_000_000.0
    span: bool = False  # full-width in the form
    advanced: bool = False  # hidden behind "More options" to keep forms short


class DateEdit(QDateEdit):
    """QDateEdit that can represent "no date" (stored as empty string)."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setCalendarPopup(True)
        self.setDisplayFormat("yyyy-MM-dd")
        self.setMinimumDate(EMPTY_DATE)
        self.setSpecialValueText(" ")
        self.setDate(EMPTY_DATE)

    def value(self) -> str:
        date = self.date()
        if date == EMPTY_DATE or date.year() < 1901:
            return ""
        return date.toString("yyyy-MM-dd")

    def set_value(self, text: str) -> None:
        if not text:
            self.setDate(EMPTY_DATE)
            return
        parsed = QDate.fromString(str(text)[:10], "yyyy-MM-dd")
        self.setDate(parsed if parsed.isValid() else EMPTY_DATE)


def build_widget(f: Field, value: Any = None) -> QWidget:
    if f.kind == "money":
        widget = QDoubleSpinBox()
        widget.setDecimals(2)
        widget.setRange(-f.maximum, f.maximum)
        widget.setGroupSeparatorShown(True)
        widget.setSuffix("")
        value = f.default if value is None else value
        widget.setValue(float(value or 0))
        return widget
    if f.kind == "float":
        widget = QDoubleSpinBox()
        widget.setDecimals(2)
        widget.setRange(0.0, f.maximum)
        value = f.default if value is None else value
        widget.setValue(float(value or 0))
        return widget
    if f.kind == "int":
        widget = QSpinBox()
        widget.setRange(int(f.minimum), int(f.maximum))
        value = f.default if value is None else value
        widget.setValue(int(value or 0))
        return widget
    if f.kind == "date":
        widget = DateEdit()
        widget.set_value(value if value is not None else (f.default or ""))
        return widget
    if f.kind == "combo":
        widget = QComboBox()
        for option_value, option_label in f.options:
            widget.addItem(option_label, option_value)
        target = value if value is not None else f.default
        if target is not None:
            index = widget.findData(target)
            widget.setCurrentIndex(index if index >= 0 else 0)
        return widget
    if f.kind == "multiline":
        widget = QPlainTextEdit()
        widget.setPlainText(str(value or f.default or ""))
        widget.setFixedHeight(84)
        return widget
    if f.kind == "check":
        widget = QCheckBox()
        raw = value if value is not None else f.default
        widget.setChecked(bool(raw) and str(raw) not in ("0", "False", ""))
        return widget

    widget = QLineEdit()
    widget.setText("" if value is None else str(value))
    if f.placeholder:
        widget.setPlaceholderText(f.placeholder)
    return widget


def read_widget(f: Field, widget: QWidget) -> Any:
    if f.kind == "money" or f.kind == "float":
        return round(float(widget.value()), 2)
    if f.kind == "int":
        return int(widget.value())
    if f.kind == "date":
        return widget.value()
    if f.kind == "combo":
        return widget.currentData()
    if f.kind == "multiline":
        return widget.toPlainText().strip()
    if f.kind == "check":
        return 1 if widget.isChecked() else 0
    return widget.text().strip()


class FormDialog(QDialog):
    """Modal add/edit form generated from a :class:`Field` list."""

    def __init__(self, title: str, fields: Sequence[Field], values: Optional[dict] = None,
                 parent: Optional[QWidget] = None, width: int = 520):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(width)
        self.fields = list(fields)
        self.widgets: dict[str, QWidget] = {}
        values = values or {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 16)
        outer.setSpacing(14)

        heading = QLabel(title)
        heading.setObjectName("SectionTitle")
        outer.addWidget(heading)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        form = QFormLayout(inner)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.setFormAlignment(Qt.AlignTop)
        form.setSpacing(11)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        for f in self.fields:
            widget = build_widget(f, values.get(f.name))
            self.widgets[f.name] = widget
            label = f.label + (" *" if f.required else "")
            form.addRow(label, widget)
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        buttons = QDialogButtonBox()
        self.save_button = buttons.addButton(tr("save"), QDialogButtonBox.AcceptRole)
        self.save_button.setObjectName("Primary")
        buttons.addButton(tr("cancel"), QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _on_accept(self) -> None:
        missing = [
            f.label for f in self.fields
            if f.required and not str(read_widget(f, self.widgets[f.name]) or "").strip()
        ]
        if missing:
            QMessageBox.warning(self, tr("warning"),
                                tr("required_field_missing", field=", ".join(missing)))
            return
        self.accept()

    def values(self) -> dict:
        return {f.name: read_widget(f, self.widgets[f.name]) for f in self.fields}

    @staticmethod
    def get_values(title: str, fields: Sequence[Field], values: Optional[dict] = None,
                   parent: Optional[QWidget] = None) -> Optional[dict]:
        dialog = FormDialog(title, fields, values, parent)
        if dialog.exec() == QDialog.Accepted:
            return dialog.values()
        return None


# --------------------------------------------------------------------------
# table helpers
# --------------------------------------------------------------------------
@dataclass
class Column:
    key: str
    width: int = 140
    align: str = "left"
    money: bool = False
    percent: bool = False
    bold: bool = False
    stretch: bool = False


class DataTable(QTableWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setShowGrid(False)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(34)
        self.horizontalHeader().setHighlightSections(False)
        self.setSortingEnabled(True)

    def configure(self, columns: Sequence[Column]) -> None:
        self.columns = list(columns)
        self.setColumnCount(len(self.columns))
        self.setHorizontalHeaderLabels([tr(c.key) for c in self.columns])
        header = self.horizontalHeader()
        for index, column in enumerate(self.columns):
            mode = QHeaderView.Stretch if column.stretch else QHeaderView.Interactive
            header.setSectionResizeMode(index, mode)
            if not column.stretch:
                self.setColumnWidth(index, column.width)
        header.setStretchLastSection(False)

    def load(self, records: Sequence[dict], formatter: Callable[[dict], list[Any]]) -> None:
        self.setSortingEnabled(False)
        self.setRowCount(0)
        for record in records:
            row = self.rowCount()
            self.insertRow(row)
            cells = formatter(record)
            for index, value in enumerate(cells):
                if index >= len(self.columns):
                    break
                column = self.columns[index]
                if isinstance(value, tuple):  # (text, color)
                    text, color = value
                else:
                    text, color = value, None
                item = QTableWidgetItem("" if text is None else str(text))
                if color:
                    item.setForeground(QColor(color))
                if column.align == "right" or column.money or column.percent:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if column.bold:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                item.setData(Qt.UserRole, record.get("id"))
                self.setItem(row, index, item)
        self.setSortingEnabled(True)

    def selected_id(self) -> Optional[int]:
        rows = self.selectionModel().selectedRows() if self.selectionModel() else []
        if not rows:
            return None
        item = self.item(rows[0].row(), 0)
        return item.data(Qt.UserRole) if item else None


# --------------------------------------------------------------------------
# CRUD page scaffold
# --------------------------------------------------------------------------
class CrudView(QWidget):
    """List page with toolbar, search, table and add/edit/delete actions."""

    changed = Signal()

    title_key = "app_name"
    subtitle_key = ""
    add_label_key = "add"
    columns: list[Column] = []
    search_placeholder_key = "search"

    def __init__(self, ctx: AppContext, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.ctx = ctx
        self.setObjectName("Root")

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 20)
        root.setSpacing(14)

        header = QVBoxLayout()
        header.setSpacing(3)
        self.title_label = QLabel(tr(self.title_key))
        self.title_label.setObjectName("PageTitle")
        header.addWidget(self.title_label)
        if self.subtitle_key:
            self.subtitle_label = subtitle(tr(self.subtitle_key))
            header.addWidget(self.subtitle_label)
        root.addLayout(header)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(9)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr(self.search_placeholder_key))
        self.search.setMaximumWidth(300)
        self.search.textChanged.connect(self._apply_filter)
        self.extra_toolbar: QHBoxLayout = toolbar
        toolbar.addWidget(self.search)
        toolbar.addStretch(1)
        self._add_extra_controls(toolbar)
        self.add_button = QPushButton(tr(self.add_label_key))
        self.add_button.setObjectName("Primary")
        self.add_button.clicked.connect(self.on_add)
        toolbar.addWidget(self.add_button)
        self.edit_button = QPushButton(tr("edit"))
        self.edit_button.clicked.connect(self.on_edit)
        toolbar.addWidget(self.edit_button)
        self.delete_button = QPushButton(tr("delete"))
        self.delete_button.setObjectName("Danger")
        self.delete_button.clicked.connect(self.on_delete)
        toolbar.addWidget(self.delete_button)
        root.addLayout(toolbar)

        self.table = DataTable()
        self.table.configure(self.columns)
        self.table.doubleClicked.connect(lambda _: self.on_edit())
        self.table.itemSelectionChanged.connect(self._selection_changed)
        root.addWidget(self.table, 1)

        self.footer = QLabel("")
        self.footer.setObjectName("Muted")
        root.addWidget(self.footer)

        self._records: list[dict] = []
        self._empty_state: Optional[EmptyState] = None

    # -- hooks for subclasses ------------------------------------------
    def _add_extra_controls(self, toolbar: QHBoxLayout) -> None:
        """Optional extra widgets (filters) placed before the buttons."""

    def fetch(self) -> list[dict]:
        return []

    def row_values(self, record: dict) -> list[Any]:
        return []

    def form_fields(self) -> list[Field]:
        return []

    def form_values(self, record: dict) -> dict:
        return dict(record)

    def on_add(self) -> None:
        values = FormDialog.get_values(tr(self.add_label_key), self.form_fields(), None, self)
        if values:
            self.create(values)
            self.after_change()

    def on_edit(self) -> None:
        record_id = self.table.selected_id()
        if record_id is None:
            return
        record = self.find_record(record_id)
        if not record:
            return
        values = FormDialog.get_values(tr("edit"), self.form_fields(),
                                       self.form_values(record), self)
        if values:
            self.update(record_id, values)
            self.after_change()

    def on_delete(self) -> None:
        record_id = self.table.selected_id()
        if record_id is None:
            return
        if QMessageBox.question(
            self, tr("confirm_delete"),
            f"{tr('confirm_delete_message')}\n\n{tr('delete_irreversible')}",
        ) == QMessageBox.Yes:
            self.delete(record_id)
            self.after_change()

    def create(self, values: dict) -> None:
        raise NotImplementedError

    def update(self, record_id: int, values: dict) -> None:
        raise NotImplementedError

    def delete(self, record_id: int) -> None:
        raise NotImplementedError

    def find_record(self, record_id: int) -> Optional[dict]:
        for record in self._records:
            if record.get("id") == record_id:
                return record
        return None

    def after_change(self) -> None:
        self.refresh()
        self.changed.emit()

    # -- rendering ------------------------------------------------------
    def refresh(self) -> None:
        self._records = self.fetch()
        self.table.load(self._records, self.row_values)
        self._apply_filter(self.search.text())
        self.update_footer()

    def update_footer(self) -> None:
        self.footer.setText(self.footer_text())

    def footer_text(self) -> str:
        return ""

    def _apply_filter(self, text: str) -> None:
        needle = (text or "").strip().lower()
        if not needle:
            for row in range(self.table.rowCount()):
                self.table.setRowHidden(row, False)
            return
        for row in range(self.table.rowCount()):
            hit = any(
                needle in (self.table.item(row, col).text().lower()
                           if self.table.item(row, col) else "")
                for col in range(self.table.columnCount())
            )
            self.table.setRowHidden(row, not hit)

    def _selection_changed(self) -> None:
        has_selection = self.table.selected_id() is not None
        self.edit_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)

    def retranslate(self) -> None:
        self.title_label.setText(tr(self.title_key))
        if self.subtitle_key and hasattr(self, "subtitle_label"):
            self.subtitle_label.setText(tr(self.subtitle_key))
        self.add_button.setText(tr(self.add_label_key))
        self.edit_button.setText(tr("edit"))
        self.delete_button.setText(tr("delete"))
        self.search.setPlaceholderText(tr(self.search_placeholder_key))
        self.table.setHorizontalHeaderLabels([tr(c.key) for c in self.columns])
        self.refresh()


# --------------------------------------------------------------------------
# small shared widgets
# --------------------------------------------------------------------------
def money_label(value: float, currency: str = "EUR", compare: Optional[float] = None) -> str:
    text = format_money(value, currency)
    return text


def today_iso() -> str:
    return _dt.date.today().isoformat()


def month_keys(count: int = 24, include_future: int = 6) -> list[str]:
    """Recent + upcoming months for combo boxes (YYYY-MM)."""
    today = _dt.date.today()
    out = []
    index = today.year * 12 + today.month - 1
    for offset in range(include_future, -count, -1):
        value = index - offset
        out.append(f"{value // 12:04d}-{value % 12 + 1:02d}")
    return out


def labeled_combo(options: list[tuple[str, str]], current: Optional[str] = None) -> QComboBox:
    combo = QComboBox()
    for value, label in options:
        combo.addItem(label, value)
    if current is not None:
        index = combo.findData(current)
        combo.setCurrentIndex(index if index >= 0 else 0)
    return combo
