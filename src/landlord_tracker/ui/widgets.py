"""Reusable UI building blocks: cards, KPI tiles, empty states and charts.

Charts are hand-drawn with QPainter instead of pulling in a heavy plotting
stack. That keeps the download small, the look consistent with the theme, and
avoids an extra dependency for a privacy-first offline app.
"""

from __future__ import annotations

from typing import Optional, Sequence

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..i18n import tr
from ..services.formatting import format_money, format_money_short
from .theme import Theme


# --------------------------------------------------------------------------
# layout helpers
# --------------------------------------------------------------------------
def card(widget: Optional[QWidget] = None, padding: int = 16,
         object_name: str = "Card", spacing: int = 12) -> QFrame:
    frame = QFrame()
    frame.setObjectName(object_name)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(padding, padding, padding, padding)
    layout.setSpacing(spacing)
    if widget is not None:
        layout.addWidget(widget)
    return frame


def hline() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setFixedHeight(1)
    line.setStyleSheet("background: rgba(120,140,170,0.25); border: none;")
    return line


def section_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("SectionTitle")
    return label


def subtitle(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("PageSubtitle")
    label.setWordWrap(True)
    return label


# --------------------------------------------------------------------------
# KPI tile
# --------------------------------------------------------------------------
class KpiCard(QFrame):
    """One number, big and readable, with an optional hint line."""

    def __init__(self, label: str, value: str = "—", hint: str = "",
                 tone: str = "neutral", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("KpiCard")
        self.setMinimumWidth(160)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 13, 16, 13)
        layout.setSpacing(3)

        self.label = QLabel(label)
        self.label.setObjectName("KpiLabel")
        self.value = QLabel(value)
        self.value.setObjectName("KpiValue")
        self.hint = QLabel(hint)
        self.hint.setObjectName("KpiHint")
        self.hint.setVisible(bool(hint))

        layout.addWidget(self.label)
        layout.addWidget(self.value)
        layout.addWidget(self.hint)
        self._tone = tone
        self.set_tone(tone)

    def set_value(self, value: str, hint: str = "", tone: Optional[str] = None) -> None:
        self.value.setText(value)
        self.hint.setText(hint)
        self.hint.setVisible(bool(hint))
        if tone is not None:
            self.set_tone(tone)

    def set_tone(self, tone: str) -> None:
        self._tone = tone
        colors = {"positive": "#2E9E63", "negative": "#D0534B",
                  "warning": "#D89A22", "neutral": None}
        color = colors.get(tone)
        if color:
            self.value.setStyleSheet(f"color: {color};")
        else:
            self.value.setStyleSheet("")


class AlertChip(QLabel):
    def __init__(self, text: str, ok: bool = False, parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self.setObjectName("AlertChipOk" if ok else "AlertChip")
        self.setWordWrap(False)


class EmptyState(QFrame):
    """Friendly first-run / no-data panel with an optional action button."""

    def __init__(self, title: str, body: str, action_text: str = "",
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.button: Optional[QPushButton] = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 34, 28, 34)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignCenter)

        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        title_label.setAlignment(Qt.AlignCenter)
        body_label = QLabel(body)
        body_label.setObjectName("Muted")
        body_label.setWordWrap(True)
        body_label.setAlignment(Qt.AlignCenter)
        body_label.setMaximumWidth(520)

        layout.addWidget(title_label)
        layout.addWidget(body_label)
        if action_text:
            self.button = QPushButton(action_text)
            self.button.setObjectName("Primary")
            row = QHBoxLayout()
            row.addStretch(1)
            row.addWidget(self.button)
            row.addStretch(1)
            layout.addLayout(row)


# --------------------------------------------------------------------------
# charts
# --------------------------------------------------------------------------
class ChartBase(QWidget):
    """Shared painting utilities: padding, gridlines, value formatting."""

    def __init__(self, theme: Theme, height: int = 220, currency: str = "EUR"):
        super().__init__()
        self.theme = theme
        self.currency = currency
        self.setMinimumHeight(height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._font = QFont()
        self._font.setPointSizeF(8.5)
        self._label_font = QFont()
        self._label_font.setPointSizeF(8.0)

    def set_currency(self, currency: str) -> None:
        self.currency = currency
        self.update()

    def set_theme(self, theme: Theme) -> None:
        self.theme = theme
        self.update()

    # -- helpers --------------------------------------------------------
    def _text(self, painter: QPainter, x: float, y: float, text: str,
              color: Optional[str] = None, font: Optional[QFont] = None,
              align=Qt.AlignLeft | Qt.AlignVCenter) -> None:
        painter.setFont(font or self._font)
        painter.setPen(QColor(color or self.theme["muted"]))
        metrics = QFontMetrics(painter.font())
        rect = QRectF(x, y - metrics.height() / 2, metrics.horizontalAdvance(text) + 2,
                      metrics.height())
        painter.drawText(rect, int(align), text)

    def _nice_scale(self, maximum: float) -> float:
        """Round the axis top up to a value whose gridlines land on round numbers."""
        if maximum <= 0:
            return 1.0
        magnitude = 10 ** (len(str(int(maximum))) - 1)
        for factor in (1, 2, 2.5, 5, 10):
            candidate = magnitude * factor
            if candidate >= maximum:
                return float(candidate)
        return float(magnitude * 10)

    def _draw_grid(self, painter: QPainter, rect: QRectF, top: float, steps: int = 5) -> None:
        # 5 steps against a 1/2/2.5/5/10 scale always yields readable labels
        # (0, 1k, 2k, 3k, 4k, 5k) instead of 1.25k / 3.75k.
        painter.setPen(QPen(QColor(self.theme["grid"]), 1))
        for i in range(steps + 1):
            y = rect.bottom() - (rect.height() * i / steps)
            painter.drawLine(int(rect.left()), int(y), int(rect.right()), int(y))
            value = top * i / steps
            self._text(painter, rect.left() - 6, y, self._compact(value),
                       align=Qt.AlignRight | Qt.AlignVCenter)

    def _compact(self, value: float) -> str:
        if abs(value) >= 1000:
            return f"{value / 1000:.0f}k"
        return f"{value:.0f}"

    def _placeholder(self, painter: QPainter, text: str) -> None:
        painter.setPen(QColor(self.theme["muted"]))
        font = QFont(self._font)
        font.setPointSizeF(10)
        painter.setFont(font)
        painter.drawText(self.rect(), int(Qt.AlignCenter), text)


class BarChart(ChartBase):
    """Vertical bars with rounded tops and value labels."""

    def __init__(self, theme: Theme, labels: Sequence[str] = (), values: Sequence[float] = (),
                 height: int = 230, currency: str = "EUR", color_index: int = 0,
                 show_values: bool = True):
        super().__init__(theme, height, currency)
        self.labels = list(labels)
        self.values = [float(v) for v in values]
        self.color_index = color_index
        self.show_values = show_values

    def set_data(self, labels: Sequence[str], values: Sequence[float]) -> None:
        self.labels = list(labels)
        self.values = [float(v) for v in values]
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if not self.values or all(v == 0 for v in self.values):
            self._placeholder(painter, tr("chart_no_data"))
            return

        left_pad, right_pad, top_pad, bottom_pad = 56, 12, 22, 40
        rect = QRectF(left_pad, top_pad, self.width() - left_pad - right_pad,
                      self.height() - top_pad - bottom_pad)
        top = self._nice_scale(max(self.values))
        self._draw_grid(painter, rect, top)

        count = len(self.values)
        slot = rect.width() / count
        bar_width = min(56.0, slot * 0.58)
        color = QColor(self.theme.chart_color(self.color_index))

        for index, value in enumerate(self.values):
            height = 0 if top <= 0 else rect.height() * (value / top)
            x = rect.left() + slot * index + (slot - bar_width) / 2
            bar = QRectF(x, rect.bottom() - height, bar_width, height)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            path = QPainterPath()
            radius = min(6.0, bar_width / 2, max(bar.height(), 0.1))
            path.addRoundedRect(bar, radius, radius)
            painter.drawPath(path)

            if self.show_values and value > 0:
                self._text(painter, bar.center().x() - 26, bar.top() - 11,
                           format_money_short(value, self.currency),
                           color=self.theme["text"], font=self._label_font,
                           align=Qt.AlignHCenter | Qt.AlignVCenter)

            label = self.labels[index] if index < len(self.labels) else ""
            painter.setFont(self._label_font)
            painter.setPen(QColor(self.theme["muted"]))
            label_rect = QRectF(x - slot * 0.2, rect.bottom() + 6, bar_width + slot * 0.4, 30)
            painter.drawText(label_rect, int(Qt.AlignHCenter | Qt.AlignTop),
                             self._elide(label, bar_width + slot * 0.4))

    def _elide(self, text: str, width: float) -> str:
        metrics = QFontMetrics(self._label_font)
        if metrics.horizontalAdvance(text) <= width:
            return text
        while text and metrics.horizontalAdvance(text + "…") > width:
            text = text[:-1]
        return text + "…"


class GroupedBarChart(ChartBase):
    """Two or more series side by side (purchase price vs current value)."""

    def __init__(self, theme: Theme, labels: Sequence[str] = (),
                 series: Optional[dict[str, Sequence[float]]] = None,
                 legend: Optional[dict[str, str]] = None,
                 height: int = 240, currency: str = "EUR"):
        super().__init__(theme, height, currency)
        self.labels = list(labels)
        self.series = {k: [float(x) for x in v] for k, v in (series or {}).items()}
        self.legend = legend or {}

    def set_data(self, labels: Sequence[str], series: dict[str, Sequence[float]]) -> None:
        self.labels = list(labels)
        self.series = {k: [float(x) for x in v] for k, v in series.items()}
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if not self.series or not self.labels:
            self._placeholder(painter, tr("chart_no_data"))
            return

        left_pad, right_pad, top_pad, bottom_pad = 56, 12, 34, 40
        rect = QRectF(left_pad, top_pad, self.width() - left_pad - right_pad,
                      self.height() - top_pad - bottom_pad)
        maximum = max((max(v) if v else 0) for v in self.series.values())
        top = self._nice_scale(maximum)
        self._draw_grid(painter, rect, top)

        keys = list(self.series)
        count = len(self.labels)
        slot = rect.width() / count
        group_width = min(96.0, slot * 0.7)
        bar_width = group_width / len(keys)

        for index in range(count):
            base_x = rect.left() + slot * index + (slot - group_width) / 2
            for k_index, key in enumerate(keys):
                values = self.series[key]
                value = values[index] if index < len(values) else 0.0
                height = 0 if top <= 0 else rect.height() * (value / top)
                bar = QRectF(base_x + bar_width * k_index, rect.bottom() - height,
                             max(bar_width - 3, 2), height)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(self.theme.chart_color(
                    [0, 1, 3, 5][k_index % 4])))
                path = QPainterPath()
                radius = min(5.0, bar.width() / 2, max(bar.height(), 0.1))
                path.addRoundedRect(bar, radius, radius)
                painter.drawPath(path)

            label = self.labels[index]
            painter.setFont(self._label_font)
            painter.setPen(QColor(self.theme["muted"]))
            label_rect = QRectF(base_x - slot * 0.1, rect.bottom() + 6, group_width + slot * 0.2, 30)
            painter.drawText(label_rect, int(Qt.AlignHCenter | Qt.AlignTop),
                             self._elide(label, group_width + slot * 0.2))

        # legend
        x = rect.left()
        for k_index, key in enumerate(keys):
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(self.theme.chart_color([0, 1, 3, 5][k_index % 4])))
            painter.drawRoundedRect(QRectF(x, 8, 11, 11), 3, 3)
            text = self.legend.get(key, key)
            self._text(painter, x + 16, 14, text, font=self._label_font)
            x += 16 + QFontMetrics(self._label_font).horizontalAdvance(text) + 22

    def _elide(self, text: str, width: float) -> str:
        metrics = QFontMetrics(self._label_font)
        if metrics.horizontalAdvance(text) <= width:
            return text
        while text and metrics.horizontalAdvance(text + "…") > width:
            text = text[:-1]
        return text + "…"


class CashflowChart(ChartBase):
    """Rent vs expenses as paired bars, with the net result as a line.

    This is the chart landlords actually stare at: am I making money this month?
    """

    NEGATIVE_COLOR = "#D0534B"
    POSITIVE_COLOR = "#2E9E63"

    def __init__(self, theme: Theme, labels: Sequence[str] = (),
                 rent: Sequence[float] = (), expenses: Sequence[float] = (),
                 net: Sequence[float] = (), height: int = 260, currency: str = "EUR"):
        super().__init__(theme, height, currency)
        self.labels = list(labels)
        self.rent = [float(v) for v in rent]
        self.expenses = [float(v) for v in expenses]
        self.net = [float(v) for v in net]

    def set_data(self, labels, rent, expenses, net) -> None:
        self.labels = list(labels)
        self.rent = [float(v) for v in rent]
        self.expenses = [float(v) for v in expenses]
        self.net = [float(v) for v in net]
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if not self.labels or not any(self.rent) and not any(self.expenses):
            self._placeholder(painter, tr("chart_no_data"))
            return

        left_pad, right_pad, top_pad, bottom_pad = 58, 14, 34, 42
        rect = QRectF(left_pad, top_pad, self.width() - left_pad - right_pad,
                      self.height() - top_pad - bottom_pad)
        top = self._nice_scale(max(max(self.rent or [0]), max(self.expenses or [0])))
        self._draw_grid(painter, rect, top)

        count = len(self.labels)
        slot = rect.width() / count
        bar_width = min(26.0, slot * 0.3)

        for index in range(count):
            center = rect.left() + slot * index + slot / 2
            for offset, values, color_index in (
                (-bar_width - 1, self.rent, 0),
                (1, self.expenses, 4),
            ):
                value = values[index] if index < len(values) else 0.0
                height = 0 if top <= 0 else rect.height() * (value / top)
                bar = QRectF(center + offset, rect.bottom() - height,
                             max(bar_width, 2), height)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(self.theme.chart_color(color_index)))
                path = QPainterPath()
                radius = min(5.0, bar.width() / 2, max(bar.height(), 0.1))
                path.addRoundedRect(bar, radius, radius)
                painter.drawPath(path)

            label = self.labels[index] if index < len(self.labels) else ""
            painter.setFont(self._label_font)
            painter.setPen(QColor(self.theme["muted"]))
            painter.drawText(QRectF(center - slot / 2, rect.bottom() + 6, slot, 26),
                             int(Qt.AlignHCenter | Qt.AlignTop), label)

        # net line
        if self.net:
            painter.setPen(QPen(QColor(self.theme["text"]), 2))
            points = []
            for index in range(min(count, len(self.net))):
                center = rect.left() + slot * index + slot / 2
                value = max(self.net[index], 0)
                y = rect.bottom() - (0 if top <= 0 else rect.height() * (value / top))
                points.append((center, y))
            for a, b in zip(points, points[1:]):
                painter.drawLine(int(a[0]), int(a[1]), int(b[0]), int(b[1]))
            painter.setBrush(QColor(self.theme.chart_color(1)))
            for x, y in points:
                painter.drawEllipse(QRectF(x - 3, y - 3, 6, 6))

        # legend
        entries = [(self.theme.chart_color(0), tr("legend_rent")),
                   (self.theme.chart_color(4), tr("legend_expenses")),
                   (self.theme.chart_color(1), tr("legend_net"))]
        x = rect.left()
        for color, text in entries:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(QRectF(x, 8, 11, 11), 3, 3)
            self._text(painter, x + 16, 14, text, font=self._label_font)
            x += 16 + QFontMetrics(self._label_font).horizontalAdvance(text) + 22


class DonutChart(ChartBase):
    """Category split with a legend; used for rent status and expenses.

    ``labels`` stay canonical (``paid``, ``late``, ``rent`` …) so colour lookup
    is reliable, while ``display_labels`` holds the translated text shown to the
    user. Mixing the two was how the rent-status colours got lost.
    """

    def __init__(self, theme: Theme, labels: Sequence[str] = (), values: Sequence[float] = (),
                 colors: Optional[dict[str, str]] = None, center_label: str = "",
                 height: int = 230, currency: str = "EUR", use_status_colors: bool = False,
                 display_labels: Optional[Sequence[str]] = None):
        super().__init__(theme, height, currency)
        self.labels = list(labels)
        self.display_labels = list(display_labels) if display_labels else list(labels)
        self.values = [float(v) for v in values]
        self.colors = colors or {}
        self.center_label = center_label
        self.use_status_colors = use_status_colors

    def set_data(self, labels: Sequence[str], values: Sequence[float],
                 center_label: str = "",
                 display_labels: Optional[Sequence[str]] = None) -> None:
        self.labels = list(labels)
        self.display_labels = list(display_labels) if display_labels else list(labels)
        self.values = [float(v) for v in values]
        if center_label:
            self.center_label = center_label
        self.update()

    def _color_for(self, index: int) -> str:
        key = self.labels[index] if index < len(self.labels) else ""
        color = self.colors.get(key)
        if not color and self.use_status_colors:
            color = self.theme.status_color(key)
        if not color:
            color = self.theme.chart_color(index)
        return color

    def _display(self, index: int) -> str:
        if index < len(self.display_labels):
            return self.display_labels[index]
        return self.labels[index] if index < len(self.labels) else ""

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        total = sum(v for v in self.values if v > 0)
        if total <= 0:
            self._placeholder(painter, tr("chart_no_data"))
            return

        size = min(self.height() - 24, self.width() * 0.5)
        ring = QRectF(14, (self.height() - size) / 2, size, size)
        thickness = size * 0.24
        start = 90 * 16
        for index, value in enumerate(self.values):
            if value <= 0:
                continue
            span = -int(360 * 16 * (value / total))
            pen = QPen(QColor(self._color_for(index)), thickness)
            pen.setCapStyle(Qt.FlatCap)
            painter.setPen(pen)
            painter.drawArc(ring.adjusted(thickness / 2, thickness / 2,
                                          -thickness / 2, -thickness / 2), start, span)
            start += span

        center = ring.center()
        if self.center_label:
            font = QFont(self._label_font)
            font.setPointSizeF(12)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QColor(self.theme["text"]))
            painter.drawText(QRectF(center.x() - size / 2, center.y() - 12, size, 24),
                             int(Qt.AlignCenter), self.center_label)

        # legend
        x = ring.right() + 26
        y = 20
        for index, _label in enumerate(self.labels):
            value = self.values[index] if index < len(self.values) else 0.0
            if value <= 0:
                continue
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(self._color_for(index)))
            painter.drawRoundedRect(QRectF(x, y, 11, 11), 3, 3)
            share = value / total
            self._text(painter, x + 17, y + 6, self._display(index),
                       color=self.theme["text"], font=self._label_font)
            self._text(painter, x + 17, y + 22,
                       f"{format_money(value, self.currency)} · {share * 100:.0f}%",
                       font=self._label_font)
            y += 34
            if y > self.height() - 20:
                break


class ProgressRow(QWidget):
    """A labeled bar with a percentage — used for occupancy and payback."""

    def __init__(self, label: str, value_text: str, ratio: Optional[float],
                 color: str = "#3E8ED0", parent: Optional[QWidget] = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(5)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.label = QLabel(label)
        self.label.setObjectName("Muted")
        self.value = QLabel(value_text)
        self.value.setStyleSheet("font-weight: 600;")
        row.addWidget(self.label)
        row.addStretch(1)
        row.addWidget(self.value)
        layout.addLayout(row)

        self.bar = QFrame()
        self.bar.setFixedHeight(8)
        self.bar.setStyleSheet(
            f"background: rgba(120,140,170,0.18); border-radius: 4px;"
        )
        self.fill = QFrame(self.bar)
        self.fill.setStyleSheet(f"background: {color}; border-radius: 4px;")
        self._ratio = 0.0
        self.set_ratio(ratio)
        layout.addWidget(self.bar)

    def set_ratio(self, ratio: Optional[float]) -> None:
        self._ratio = 0.0 if ratio is None else max(0.0, min(1.0, ratio))
        self._resize_fill()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._resize_fill()

    def _resize_fill(self) -> None:
        width = max(0, int(self.bar.width() * self._ratio))
        self.fill.setGeometry(0, 0, width, self.bar.height())
