"""Zone 列表面板。"""

import copy
from pathlib import Path
from typing import Callable, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..models import Project, SampleEntry, ZoneEntry


class ZoneListPanel(QGroupBox):
    """展示工程内所有 Zone，支持增删/复制/导入音源。"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("Zone 列表", parent)
        self._project: Optional[Project] = None
        self._on_selection_changed: Optional[Callable[[Optional[ZoneEntry]], None]] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._table = QTableWidget()
        self._table.setMinimumHeight(300)
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels(["名称", "音源采样", "根音", "Note 范围", "Vel 范围", "模式", "校验"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setFocusPolicy(Qt.NoFocus)  # 默认不显示焦点光标
        self._table.setStyleSheet(
            "QTableWidget { gridline-color: transparent; border: none; }"
            "QTableWidget::item { border: none; outline: none; padding-left: 4px; }"
            "QTableWidget::item:selected { background-color: #3a3a3a; color: #ffffff; }"
            "QTableWidget::item:focus { border: none; outline: none; }"
        )
        for col in range(7):
            self._table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.itemSelectionChanged.connect(self._emit_selection)
        self._table.itemChanged.connect(self._on_item_changed)
        self._table.doubleClicked.connect(self._on_double_click)
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_context_menu)
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

    def _get_sample(self, sample_id: str) -> Optional[SampleEntry]:
        return self._project.get_sample(sample_id) if self._project else None

    def refresh(self) -> None:
        selected_id = None
        rows = self._table.selectionModel().selectedRows()
        if rows:
            item = self._table.item(rows[0].row(), 0)
            if item is not None:
                selected_id = item.data(Qt.UserRole)

        self._table.setRowCount(0)
        if self._project is None:
            return
        for zone in self._project.zones:
            row = self._table.rowCount()
            self._table.insertRow(row)
            name_item = QTableWidgetItem(zone.name or f"Zone {row + 1}")
            name_item.setData(Qt.UserRole, zone.id)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)  # 默认不可编辑
            self._table.setItem(row, 0, name_item)

            sample = self._get_sample(zone.sample_id)
            sample_name = sample.name if sample else "(丢失)"
            self._table.setItem(row, 1, QTableWidgetItem(sample_name))
            self._table.setItem(row, 2, QTableWidgetItem(str(zone.root_note)))
            self._table.setItem(row, 3, QTableWidgetItem(f"{zone.min_note}-{zone.max_note}"))
            self._table.setItem(row, 4, QTableWidgetItem(f"{zone.min_vel}-{zone.max_vel}"))
            self._table.setItem(row, 5, QTableWidgetItem(zone.poly_mode))

            errs = zone.validate()
            status_item = QTableWidgetItem("OK" if not errs else "错误")
            if errs:
                status_item.setForeground(Qt.red)
                status_item.setToolTip("\n".join(errs))
            else:
                status_item.setForeground(Qt.green)
            self._table.setItem(row, 6, status_item)

        if selected_id is not None:
            self._table.blockSignals(True)
            self._select_zone(selected_id)
            self._table.blockSignals(False)

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

    def _select_zone(self, zone_id: str) -> None:
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item and item.data(Qt.UserRole) == zone_id:
                self._table.selectRow(row)
                break

    def _emit_selection(self) -> None:
        if self._on_selection_changed:
            self._on_selection_changed(self.selected_zone())

    def _on_context_menu(self, pos) -> None:
        if self._project is None:
            return
        menu = QMenu(self)
        add_action = menu.addAction("新建 Zone")
        duplicate_action = menu.addAction("复制 Zone")
        delete_action = menu.addAction("删除 Zone")

        # 只有点击到有效行时才启用复制/删除
        item = self._table.itemAt(pos)
        has_selection = item is not None
        duplicate_action.setEnabled(has_selection)
        delete_action.setEnabled(has_selection)

        action = menu.exec(self._table.viewport().mapToGlobal(pos))
        if action == add_action:
            self._on_add()
        elif action == duplicate_action:
            self._on_duplicate()
        elif action == delete_action:
            self._on_remove()

    def _on_double_click(self, index) -> None:
        """双击名称列进入编辑模式。"""
        if index.column() != 0:
            return
        row = index.row()
        self._table.editItem(self._table.item(row, 0))

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        """列表项编辑完成后同步到 Zone 名称。"""
        if item.column() != 0 or self._project is None:
            return
        zone_id = item.data(Qt.UserRole)
        zone = self._project.get_zone(zone_id)
        if zone is None:
            return
        new_name = item.text().strip()
        if new_name and new_name != zone.name:
            zone.name = new_name
            if self._on_selection_changed:
                self._on_selection_changed(zone)

    def _on_import_wav(self) -> None:
        if self._project is None:
            return
        files, _ = QFileDialog.getOpenFileNames(
            self, "导入 WAV 音源", "", "WAV 文件 (*.wav)"
        )
        imported: List[SampleEntry] = []
        for path in files:
            try:
                sample = SampleEntry.from_wav(path)
                self._project.add_sample(sample)
                imported.append(sample)
            except Exception as e:
                QMessageBox.warning(self, "导入失败", f"{path}\n{e}")
        if imported and self._on_selection_changed:
            self.refresh()
            self._emit_selection()

    def _next_note_range(self) -> tuple[int, int, int]:
        """计算新建 Zone 的默认 note 范围与根音：接在上一个 Zone 后面，默认两个八度。"""
        if not self._project or not self._project.zones:
            root = 60
            min_note = max(0, root - 12)
            max_note = min(127, root + 12)
            return root, min_note, max_note

        last_max = max(z.max_note for z in self._project.zones)
        min_note = min(127, last_max + 1)
        max_note = min(127, min_note + 24)
        # 如果空间不足，从 0 开始
        if min_note > 127 - 12:
            min_note = 0
            max_note = 24
        root = min(127, min_note + 12)
        return root, min_note, max_note

    def _on_add(self) -> None:
        if self._project is None:
            return
        if not self._project.samples:
            QMessageBox.information(self, "提示", "请先导入 WAV 音源（通过文件菜单或直接把 WAV 放入工程目录）")
            return

        root, min_note, max_note = self._next_note_range()
        sample = self._project.samples[-1]
        zone = ZoneEntry(
            sample_id=sample.id,
            name=f"Zone {len(self._project.zones) + 1}",
            root_note=root,
            min_note=min_note,
            max_note=max_note,
            min_vel=0,
            max_vel=127,
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
        new_zone = copy.deepcopy(zone)
        new_zone.id = f"{new_zone.id}_dup"
        new_zone.name = f"{new_zone.name or 'Zone'} 副本"
        self._project.add_zone(new_zone)
        self.refresh()
        self._select_zone(new_zone.id)
        self._emit_selection()

    def get_all_zones(self) -> List[ZoneEntry]:
        return list(self._project.zones) if self._project else []
