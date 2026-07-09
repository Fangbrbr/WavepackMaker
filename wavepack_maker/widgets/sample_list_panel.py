"""Sample 列表面板。"""

from pathlib import Path
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

from ..models import Project, SampleEntry


class SampleListPanel(QGroupBox):
    """展示工程内所有 Sample，支持导入、删除、重新定位。"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("采样列表", parent)
        self._project: Optional[Project] = None
        self._on_selection_changed: Optional[Callable[[Optional[SampleEntry]], None]] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["名称", "路径", "采样率", "通道", "位深"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.itemSelectionChanged.connect(self._emit_selection)
        layout.addWidget(self._table)

        btn_layout = QHBoxLayout()
        self._import_btn = QPushButton("导入 WAV")
        self._import_btn.setToolTip("导入一个或多个 WAV 文件作为采样")
        self._import_btn.clicked.connect(self._on_import)
        self._remove_btn = QPushButton("删除")
        self._remove_btn.clicked.connect(self._on_remove)
        self._locate_btn = QPushButton("重新定位")
        self._locate_btn.setToolTip("当 WAV 文件移动后，手动重新指定路径")
        self._locate_btn.clicked.connect(self._on_locate)
        btn_layout.addWidget(self._import_btn)
        btn_layout.addWidget(self._remove_btn)
        btn_layout.addWidget(self._locate_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def set_project(self, project: Project) -> None:
        self._project = project
        self.refresh()

    def set_on_selection_changed(self, callback: Callable[[Optional[SampleEntry]], None]) -> None:
        self._on_selection_changed = callback

    def refresh(self) -> None:
        self._table.setRowCount(0)
        if self._project is None:
            return
        for sample in self._project.samples:
            row = self._table.rowCount()
            self._table.insertRow(row)
            name_item = QTableWidgetItem(sample.name)
            name_item.setData(Qt.UserRole, sample.id)
            self._table.setItem(row, 0, name_item)
            self._table.setItem(row, 1, QTableWidgetItem(sample.file_path))
            self._table.setItem(row, 2, QTableWidgetItem(str(sample.sample_rate)))
            self._table.setItem(row, 3, QTableWidgetItem(str(sample.channels)))
            self._table.setItem(row, 4, QTableWidgetItem(str(sample.bits)))

    def selected_sample(self) -> Optional[SampleEntry]:
        rows = self._table.selectionModel().selectedRows()
        if not rows or self._project is None:
            return None
        row = rows[0].row()
        item = self._table.item(row, 0)
        if item is None:
            return None
        sample_id = item.data(Qt.UserRole)
        return self._project.get_sample(sample_id)

    def _emit_selection(self) -> None:
        if self._on_selection_changed:
            self._on_selection_changed(self.selected_sample())

    def _on_import(self) -> None:
        if self._project is None:
            return
        from PySide6.QtWidgets import QFileDialog

        files, _ = QFileDialog.getOpenFileNames(
            self, "导入 WAV 采样", "", "WAV 文件 (*.wav)"
        )
        for path in files:
            try:
                sample = SampleEntry.from_wav(path)
                self._project.add_sample(sample)
            except Exception as e:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "导入失败", f"{path}\n{e}")
        self.refresh()
        self._emit_selection()

    def _on_remove(self) -> None:
        sample = self.selected_sample()
        if sample is None or self._project is None:
            return
        self._project.remove_sample(sample.id)
        self.refresh()
        self._emit_selection()

    def _on_locate(self) -> None:
        sample = self.selected_sample()
        if sample is None:
            return
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            self, "重新定位采样文件", sample.file_path, "WAV 文件 (*.wav)"
        )
        if path:
            sample.file_path = path
            try:
                updated = SampleEntry.from_wav(path)
                sample.sample_rate = updated.sample_rate
                sample.channels = updated.channels
                sample.bits = updated.bits
                sample.nframes = updated.nframes
            except Exception:
                pass
            self.refresh()
