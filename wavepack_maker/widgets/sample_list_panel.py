"""Sample 列表面板。"""

from pathlib import Path
from typing import Callable, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..models import Project, SampleEntry


class SampleListPanel(QGroupBox):
    """展示工程目录 samples/ 下的所有 WAV 音源，支持点击预览。"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("采样清单", parent)
        self._project: Optional[Project] = None
        self._on_selection_changed: Optional[Callable[[Optional[SampleEntry]], None]] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._table = QTableWidget()
        self._table.setMinimumWidth(120)
        self._table.setMaximumWidth(220)
        self._table.setColumnCount(2)
        self._table.setHorizontalHeaderLabels(["#", "名称"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setFocusPolicy(Qt.NoFocus)
        self._table.setStyleSheet("QTableWidget::item { border: none; outline: none; }")
        self._table.itemSelectionChanged.connect(self._emit_selection)
        layout.addWidget(self._table)

    def set_project(self, project: Project) -> None:
        self._project = project
        self.refresh()

    def set_on_selection_changed(self, callback: Callable[[Optional[SampleEntry]], None]) -> None:
        self._on_selection_changed = callback

    def refresh(self) -> None:
        selected_id = None
        rows = self._table.selectionModel().selectedRows()
        if rows:
            item = self._table.item(rows[0].row(), 1)
            if item is not None:
                selected_id = item.data(Qt.UserRole)

        self._table.setRowCount(0)
        if self._project is None:
            return
        for idx, sample in enumerate(self._project.samples, start=1):
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(str(idx)))

            name_item = QTableWidgetItem(sample.name)
            name_item.setData(Qt.UserRole, sample.id)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self._table.setItem(row, 1, name_item)

        if selected_id is not None:
            self._table.blockSignals(True)
            self.select_sample(selected_id)
            self._table.blockSignals(False)

    def selected_sample(self) -> Optional[SampleEntry]:
        rows = self._table.selectionModel().selectedRows()
        if not rows or self._project is None:
            return None
        row = rows[0].row()
        item = self._table.item(row, 1)
        if item is None:
            return None
        sample_id = item.data(Qt.UserRole)
        return self._project.get_sample(sample_id)

    def select_sample(self, sample_id: str) -> None:
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 1)
            if item and item.data(Qt.UserRole) == sample_id:
                self._table.selectRow(row)
                break

    def _emit_selection(self) -> None:
        if self._on_selection_changed:
            self._on_selection_changed(self.selected_sample())
