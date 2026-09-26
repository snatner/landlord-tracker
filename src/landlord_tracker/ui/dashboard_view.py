"""Dashboard: the visual answer to "what do I actually own and is it working?"

Twelve KPI tiles, six charts and a renovation payback watchlist, all computed
from the local database by :mod:`landlord_tracker.services.dashboard`.
"""

from __future__ import annotations

import datetime as _dt
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..context import AppContext
from ..i18n import tr
from ..services import calculations as calc
from ..services.dashboard import DashboardData, build_dashboard
from ..services.formatting import format_money, format_percent
from .base import Column, DataTable
from .widgets import (
    AlertChip,
    BarChart,
    CashflowChart,
    DonutChart,
    EmptyState,
    GroupedBarChart,
    KpiCard,
    card,
    hline,
    section_title,
)
from .theme import CHART_COLORS


class ChartPanel(QFrame):
    """A titled card wrapping one chart."""

    def __init__(self, title_key: str, chart: QWidget, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.title_key = title_key
        self.setObjectName("Card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 13, 16, 13)
        layout.setSpacing(8)
        self.title = QLabel(tr(title_key))
        self.title.setObjectName("ChartTitle")
        layout.addWidget(self.title)
        self.chart = chart
        layout.addWidget(chart)


class DashboardView(QWidget):
    def __init__(self, ctx: AppContext, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.ctx = ctx
        self.setObjectName("Root")
        self._data: Optional[DashboardData] = None
        self._kpi_cards: dict[str, KpiCard] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        self.container = QWidget()
        self.container.setObjectName("Root")
        scroll.setWidget(self.container)

        self.root = QVBoxLayout(self.container)
        self.root.setContentsMargins(26, 22, 26, 26)
        self.root.setSpacing(16)

        self._build_header()
        self._build_alerts()
        self._build_kpis()
        self._build_charts()
        self._build_renovations()
        self.empty_state = EmptyState(
            tr("empty_welcome_title"), tr("empty_welcome_body"), tr("add_first_property")
        )
        self.empty_state.setVisible(False)
        self.root.addWidget(self.empty_state)
        self.root.addStretch(1)

    # ------------------------------------------------------------------
    def _build_header(self) -> None:
        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.title = QLabel(tr("nav_dashboard"))
        self.title.setObjectName("PageTitle")
        self.subtitle = QLabel("")
        self.subtitle.setObjectName("PageSubtitle")
        titles.addWidget(self.title)
        titles.addWidget(self.subtitle)
        header.addLayout(titles)
        header.addStretch(1)

        self.property_filter = QComboBox()
        self.property_filter.setMinimumWidth(190)
        self.property_filter.currentIndexChanged.connect(lambda _: self.refresh())
        header.addWidget(self.property_filter)

        self.months_filter = QComboBox()
        for count in (6, 12, 24, 36):
            self.months_filter.addItem(tr("last_months", count=count), count)
        self.months_filter.setCurrentIndex(1)
        self.months_filter.currentIndexChanged.connect(lambda _: self.refresh())
        header.addWidget(self.months_filter)

        refresh_button = QPushButton(tr("refresh"))
        refresh_button.clicked.connect(self.refresh)
        header.addWidget(refresh_button)
        self.root.addLayout(header)

    def _build_alerts(self) -> None:
        self.alerts_row = QHBoxLayout()
        self.alerts_row.setSpacing(8)
        self.root.addLayout(self.alerts_row)

    def _build_kpis(self) -> None:
        self.kpi_grid = QGridLayout()
        self.kpi_grid.setSpacing(12)
        self.root.addLayout(self.kpi_grid)
        self.kpi_order = [
            "portfolio_value", "rent_collected", "arrears", "net_cashflow",
            "occupancy", "rent_collection_rate", "capital_gain", "renovation_invested",
            "monthly_expenses", "active_tenants", "gross_yield", "annual_rent_roll",
        ]
        self.kpi_hints = {
            "rent_collected": "rent_expected",
            "rent_collection_rate": "rent_expected",
            "capital_gain": "purchase_total",
            "net_cashflow": "monthly_expenses",
            "active_tenants": "occupancy",
        }
        for index, key in enumerate(self.kpi_order):
            tile = KpiCard(tr(key))
            self._kpi_cards[key] = tile
            self.kpi_grid.addWidget(tile, index // 4, index % 4)

    def _build_charts(self) -> None:
        t = self.ctx.theme
        currency = self.ctx.currency

        self.cashflow_chart = CashflowChart(t, currency=currency, height=270)
        self.cashflow_panel = ChartPanel("chart_cashflow", self.cashflow_chart)

        self.portfolio_chart = BarChart(t, currency=currency, height=250, color_index=0)
        self.portfolio_panel = ChartPanel("chart_portfolio_value", self.portfolio_chart)

        self.rent_status_chart = DonutChart(t, currency=currency, height=240,
                                            use_status_colors=True)
        self.rent_status_panel = ChartPanel("chart_rent_status", self.rent_status_chart)

        self.purchase_chart = GroupedBarChart(
            t, currency=currency, height=250,
            legend={"purchase": tr("legend_purchase"), "current": tr("legend_current")},
        )
        self.purchase_panel = ChartPanel("chart_purchase_vs_value", self.purchase_chart)

        self.expense_chart = DonutChart(t, currency=currency, height=240)
        self.expense_panel = ChartPanel("chart_expenses_by_category", self.expense_chart)

        self.ranking_chart = BarChart(t, currency=currency, height=250, color_index=1)
        self.ranking_panel = ChartPanel("chart_property_ranking", self.ranking_chart)

        charts = QGridLayout()
        charts.setSpacing(14)
        charts.addWidget(self.cashflow_panel, 0, 0, 1, 2)
        charts.addWidget(self.rent_status_panel, 0, 2, 1, 1)
        charts.addWidget(self.portfolio_panel, 1, 0, 1, 2)
        charts.addWidget(self.purchase_panel, 1, 2, 1, 1)
        charts.addWidget(self.ranking_panel, 2, 0, 1, 2)
        charts.addWidget(self.expense_panel, 2, 2, 1, 1)
        charts.setColumnStretch(0, 3)
        charts.setColumnStretch(1, 3)
        charts.setColumnStretch(2, 2)
        self.root.addLayout(charts)

    def _build_renovations(self) -> None:
        panel = card()
        layout = panel.layout()
        header = QHBoxLayout()
        header.addWidget(section_title(tr("renovation_watchlist")))
        header.addStretch(1)
        hint = QLabel(tr("renovation_payback_hint"))
        hint.setObjectName("Muted")
        header.addWidget(hint)
        layout.addLayout(header)

        self.reno_table = DataTable()
        self.reno_table.configure([
            Column("renovation", stretch=True),
            Column("property", 170),
            Column("status", 110),
            Column("budget", 120, money=True),
            Column("actual", 120, money=True),
            Column("variance", 120, money=True),
            Column("monthly_uplift", 130, money=True),
            Column("payback_months", 140, align="right", bold=True),
        ])
        self.reno_table.setMinimumHeight(190)
        layout.addWidget(self.reno_table)
        self.reno_panel = panel
        self.root.addWidget(panel)

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        data = self._refresh_property_filter_and_build()
        self._data = data
        has_data = bool(self.ctx.db.properties(include_inactive=False))
        self.empty_state.setVisible(not has_data)
        self._render(data, has_data)

    def _refresh_property_filter_and_build(self) -> DashboardData:
        db = self.ctx.db
        current = self.property_filter.currentData()
        if self.property_filter.count() == 0:
            self.property_filter.blockSignals(True)
            self.property_filter.addItem(tr("all_properties"), None)
            for prop in db.properties(include_inactive=False):
                self.property_filter.addItem(prop["name"], prop["id"])
            self.property_filter.blockSignals(False)
            current = None
        months = int(self.months_filter.currentData() or 12)
        return build_dashboard(db, months=months, property_id=current)

    def _render(self, data: DashboardData, has_data: bool) -> None:
        currency = self.ctx.currency
        self.subtitle.setText(
            f"{tr('this_month')} · {_dt.date.today().strftime('%B %Y')}" if has_data
            else tr("privacy_line")
        )

        # alerts
        while self.alerts_row.count():
            item = self.alerts_row.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        if data.alerts:
            for code in data.alerts:
                self.alerts_row.addWidget(AlertChip(tr(code)))
        else:
            self.alerts_row.addWidget(AlertChip(tr("all_clear"), ok=True))
        self.alerts_row.addStretch(1)

        # KPIs
        for key, tile in self._kpi_cards.items():
            value = data.kpi(key)
            kind = next((k.kind for k in data.kpis if k.key == key), "money")
            hint_key = self.kpi_hints.get(key)
            hint = ""
            if hint_key:
                hint_value = data.kpi(hint_key)
                hint = f"{tr(hint_key)}: {format_money(hint_value, currency)}" \
                    if hint_key != "occupancy" else f"{tr('occupancy')}: {format_percent(hint_value)}"
            tone = "neutral"
            if key in ("net_cashflow", "capital_gain") and value is not None:
                tone = "positive" if value >= 0 else "negative"
            if key == "arrears" and value:
                tone = "warning"
            if key == "rent_collection_rate" and value is not None:
                tone = "positive" if value >= 0.95 else ("warning" if value >= 0.8 else "negative")
            tile.set_value(self._format_kpi(key, value, kind, currency), hint, tone)

        # charts
        cashflow = data.charts.get("cashflow")
        if cashflow:
            self.cashflow_chart.set_data(
                [calc.month_label(p, self.ctx.language) for p in cashflow.labels],
                cashflow.series.get("rent", []),
                cashflow.series.get("expenses", []),
                cashflow.series.get("net", []),
            )
        portfolio = data.charts.get("portfolio_value")
        if portfolio:
            self.portfolio_chart.set_data(portfolio.labels, portfolio.values)
        purchase = data.charts.get("purchase_vs_value")
        if purchase:
            self.purchase_chart.set_data(purchase.labels, purchase.series)
        rent_status = data.charts.get("rent_status")
        if rent_status:
            # canonical keys drive the colours, translated text is only shown
            self.rent_status_chart.set_data(
                rent_status.labels, rent_status.values,
                center_label=format_money(sum(rent_status.values), currency),
                display_labels=[tr(f"rent_status_{name}") for name in rent_status.labels],
            )
        expenses = data.charts.get("expenses_by_category")
        if expenses:
            self.expense_chart.set_data(
                expenses.labels, expenses.values,
                center_label=format_money(sum(expenses.values), currency),
                display_labels=[tr(f"expense_cat_{name}") for name in expenses.labels],
            )
        ranking = data.charts.get("property_ranking")
        if ranking:
            self.ranking_chart.set_data(ranking.labels, ranking.values)

        # renovation watchlist
        rows = []
        for reno in data.renovations:
            # With no spending logged there is nothing to compare the budget
            # against; a minus-budget figure would read as a saving.
            if reno.actual > 0.01:
                variance_text = format_money(reno.variance, currency)
                tone = "#D0534B" if reno.variance > 0.01 else (
                    "#2E9E63" if reno.variance < -0.01 else None)
            else:
                variance_text, tone = "—", None
            payback = (f"{reno.payback_months:.0f}" if reno.payback_months is not None
                       else tr("payback_unknown"))
            rows.append({
                "id": id(reno),
                "renovation": reno.title,
                "property": reno.property_name,
                "status": tr(f"reno_status_{reno.status}"),
                "budget": format_money(reno.budget, currency),
                "actual": format_money(reno.actual, currency),
                "variance": variance_text,
                "monthly_uplift": format_money(reno.monthly_uplift, currency),
                "payback_months": payback,
            })
        self.reno_table.load(rows, lambda r: [
            r["renovation"], r["property"], r["status"], r["budget"], r["actual"],
            r["variance"], r["monthly_uplift"], r["payback_months"],
        ])

        self.reno_panel.setVisible(bool(rows))

    def _format_kpi(self, key: str, value: Optional[float], kind: str, currency: str) -> str:
        if value is None:
            return "—"
        if kind == "money":
            if key in ("annual_rent_roll", "portfolio_value", "purchase_total",
                       "renovation_invested"):
                return format_money(value, currency, decimals=0)
            return format_money(value, currency)
        if kind == "percent":
            return format_percent(value)
        if kind == "count":
            return f"{int(value)}"
        return str(value)

    def retranslate(self) -> None:
        self.title.setText(tr("nav_dashboard"))
        for key, tile in self._kpi_cards.items():
            tile.label.setText(tr(key))
        for panel in (self.cashflow_panel, self.portfolio_panel, self.rent_status_panel,
                      self.purchase_panel, self.expense_panel, self.ranking_panel):
            panel.title.setText(tr(panel.title_key))
        self.purchase_chart.legend = {"purchase": tr("legend_purchase"),
                                      "current": tr("legend_current")}
        self.months_filter.blockSignals(True)
        for index, count in enumerate((6, 12, 24, 36)):
            self.months_filter.setItemText(index, tr("last_months", count=count))
        self.months_filter.blockSignals(False)
        self.property_filter.setItemText(0, tr("all_properties"))
        self.refresh()
