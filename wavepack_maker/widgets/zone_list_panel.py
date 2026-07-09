"""Zone 列表面板。"""

from typing import Callable, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..models import Project, SampleEntry, ZoneEntry


class ZoneListPanel(QGroupBox):
    """展示工程内所有 Zone，支持增删。"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("Zone 列表", parent)
        self._project: Optional[Project] = None
        self._on_selection_changed: Optional[Callable[[Optional[ZoneEntry]], None]] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(["名称", "采样", "根音", "Note 范围", "Vel 范围", "模式"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.itemSelectionChanged.connect(self._emit_selection)
        layout.addWidget(self._table)

        btn_layout = QHBoxLayout()
        self._add_btn = QPushButton("添加 Zone")
        self._add_btn.clicked.connect(self._on_add)
        self._remove_btn = QPushButton("删除")
        self._remove_btn.clicked.connect(self._on_remove)
        self._duplicate_btn = QPushButton("复制")
        self._duplicate_btn.clicked.connect(self._on_duplicate)
        btn_layout.addWidget(self._add_btn)
        btn_layout.addWidget(self._remove_btn)
        btn_layout.addWidget(self._duplicate_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def set_project(self, project: Project) -> None:
        self._project = project
        self.refresh()

    def set_on_selection_changed(self, callback: Callable[[Optional[ZoneEntry]], None]) -> None:
        self._on_selection_changed = callback

    def refresh(self) -> None:
        self._table.setRowCount(0)
        if self._project is None:
            return
        for zone in self._project.zones:
            row = self._table.rowCount()
            self._table.insertRow(row)
            name_item = QTableWidgetItem(zone.name or f"Zone {row + 1}")
            name_item.setData(Qt.UserRole, zone.id)
            self._table.setItem(row, 0, name_item)

            sample = self._project.get_sample(zone.sample_id)
            sample_name = sample.name if sample else "(丢失)"
            self._table.setItem(row, 1, QTableWidgetItem(sample_name))
            self._table.setItem(row, 2, QTableWidgetItem(str(zone.root_note)))
            self._table.setItem(row, 3, QTableWidgetItem(f"{zone.min_note}-{zone.max_note}"))
            self._table.setItem(row, 4, QTableWidgetItem(f"{zone.min_vel}-{zone.max_vel}"))
            self._table.setItem(row, 5, QTableWidgetItem(zone.poly_mode))

    def selected_zone(self) -> Optional[ZoneEntry]:
        rows = self._table.selectionModel().selectedRows()
        if not rows or self._project is None:
            return None
        row = rows[0].row()
        item = self._table.item(row, 0)
        if item is None:
            return None
        zone_id = item.data(Qt.UserRole)
        return self._project.get_zone(zone_id)

    def _emit_selection(self) -> None:
        if self._on_selection_changed:
            self._on_selection_changed(self.selected_zone())

    def _on_add(self) -> None:
        if self._project is None or not self._project.samples:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "提示", "请先导入 WAV 采样")
            return

        sample = self._project.samples[0]
        zone = ZoneEntry(
            sample_id=sample.id,
            name=f"Zone {len(self._project.zones) + 1}",
            root_note=sample.root_note,
            min_note=max(0, sample.root_note - 6),
            max_note=min(127, sample.root_note + 6),
        )
        self._project.add_zone(zone)
        self.refresh()
        self._select_zone(zone.id)
        self._emit_selection()

    def _on_remove(self) -> None:
        zone = self.selected_zone()
        if zone is None or self._project is None:
            return
        self._project.remove_zone(zone.id)
        self.refresh()
        self._emit_selection()

    def _on_duplicate(self) -> None:
        zone = self.selected_zone()
        if zone is None or self._project is None:
            return
        import copy
        new_zone = copy.deepcopy(zone)
        new_zone.id = f"{new_zone.id}_dup"
        new_zone.name = f"{new_zone.name or 'Zone'} 副本"
        self._project.add_zone(new_zone)
        self.refresh()
        self._select_zone(new_zone.id)
        self._emit_selection()

    def _select_zone(self, zone_id: str) -> None:
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item and item.data(Qt.UserRole) == zone_id:
                self._table.selectRow(row)
                break

    def get_all_zones(self) -> List[ZoneEntry]:
        return list(self._project.zones) if self._project else []
