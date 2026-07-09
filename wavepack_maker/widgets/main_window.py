"""WavePack Maker 主窗口。"""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..audio_player import AudioPlayer
from ..builder import WavePackBuilder
from ..models import Project, ProjectMetadata, SampleEntry, ZoneEntry
from ..project_io import load_project, save_project, suggest_project_name
from ..validator import ValidationError, WavePackValidator
from .metadata_panel import MetadataPanel
from .piano_roll import PianoRoll
from .sample_list_panel import SampleListPanel
from .waveform_view import WaveformView
from .zone_editor import ZoneEditor
from .zone_list_panel import ZoneListPanel


class MainWindow(QMainWindow):
    """WavePack Maker 主界面。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("WavePack Maker")
        self.setMinimumSize(1200, 800)

        self._project = Project()
        self._project_file_path: Optional[str] = None
        self._last_save_state: Optional[dict] = None
        self._audio_player = AudioPlayer()

        self._setup_menu()
        self._setup_central()
        self._setup_statusbar()
        self._new_project()

    def _setup_menu(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("文件(&F)")
        self._new_action = QAction("新建工程(&N)", self)
        self._new_action.setShortcut(QKeySequence.StandardKey.New)
        self._new_action.triggered.connect(self._new_project)
        file_menu.addAction(self._new_action)

        self._open_action = QAction("打开工程(&O)...", self)
        self._open_action.setShortcut(QKeySequence.StandardKey.Open)
        self._open_action.triggered.connect(self._open_project)
        file_menu.addAction(self._open_action)

        self._save_action = QAction("保存工程(&S)", self)
        self._save_action.setShortcut(QKeySequence.StandardKey.Save)
        self._save_action.triggered.connect(self._save_project)
        file_menu.addAction(self._save_action)

        self._save_as_action = QAction("另存为(&A)...", self)
        self._save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        self._save_as_action.triggered.connect(self._save_project_as)
        file_menu.addAction(self._save_as_action)

        file_menu.addSeparator()

        self._import_action = QAction("导入 WAV 到工程(&I)...", self)
        self._import_action.triggered.connect(self._import_wav)
        file_menu.addAction(self._import_action)

        self._export_action = QAction("导出 .wavepack(&E)...", self)
        self._export_action.triggered.connect(self._export_wavepack)
        file_menu.addAction(self._export_action)

        file_menu.addSeparator()

        self._exit_action = QAction("退出(&X)", self)
        self._exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self._exit_action.triggered.connect(self.close)
        file_menu.addAction(self._exit_action)

        help_menu = menu_bar.addMenu("帮助(&H)")
        self._about_action = QAction("关于(&A)", self)
        self._about_action.triggered.connect(self._show_about)
        help_menu.addAction(self._about_action)

    def _setup_central(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)

        splitter = QSplitter(Qt.Vertical)
        main_layout.addWidget(splitter)

        # 上方面板：元数据 + Zone 编辑器 + 列表
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)

        left_splitter = QSplitter(Qt.Horizontal)
        top_layout.addWidget(left_splitter)

        # 左侧：Sample 列表 + Zone 列表
        list_widget = QWidget()
        list_layout = QVBoxLayout(list_widget)
        list_layout.setContentsMargins(0, 0, 0, 0)
        self._sample_panel = SampleListPanel()
        self._sample_panel.set_on_selection_changed(self._on_sample_selected)
        list_layout.addWidget(self._sample_panel)
        self._zone_list_panel = ZoneListPanel()
        self._zone_list_panel.set_on_selection_changed(self._on_zone_selected)
        list_layout.addWidget(self._zone_list_panel)
        left_splitter.addWidget(list_widget)

        # 中间：元数据
        self._metadata_panel = MetadataPanel()
        left_splitter.addWidget(self._metadata_panel)

        # 右侧：Zone 编辑器
        self._zone_editor = ZoneEditor()
        self._zone_editor.set_on_changed(self._on_zone_edited)
        self._zone_editor.set_on_play(self._on_play_sample)
        self._zone_editor.set_on_set_loop(self._on_apply_loop)
        left_splitter.addWidget(self._zone_editor)

        left_splitter.setSizes([300, 350, 450])
        splitter.addWidget(top_widget)

        # 下方：波形 + 钢琴卷帘
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        self._waveform_view = WaveformView()
        bottom_layout.addWidget(self._waveform_view)

        self._piano_roll = PianoRoll()
        bottom_layout.addWidget(self._piano_roll)

        splitter.addWidget(bottom_widget)
        splitter.setSizes([500, 250])

    def _setup_statusbar(self) -> None:
        self._status_label = QLabel("就绪")
        self.statusBar().addWidget(self._status_label)
        self._project_label = QLabel("未保存")
        self.statusBar().addPermanentWidget(self._project_label)

    # ------------------------------------------------------------------
    # 工程生命周期
    # ------------------------------------------------------------------
    def _new_project(self) -> None:
        if not self._maybe_save_dirty():
            return
        self._project = Project(metadata=ProjectMetadata())
        self._project_file_path = None
        self._last_save_state = self._project.to_dict()
        self._bind_project()
        self._update_title()
        self._update_status()

    def _open_project(self) -> None:
        if not self._maybe_save_dirty():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "打开 WavePack 工程", "", "WavePack 工程 (*.wpp)"
        )
        if not path:
            return
        try:
            self._project = load_project(path)
            self._project_file_path = path
            self._last_save_state = self._project.to_dict()
            self._bind_project()
            self._update_title()
            self._update_status()
        except Exception as e:
            QMessageBox.critical(self, "打开失败", str(e))

    def _save_project(self) -> bool:
        if self._project_file_path is None:
            return self._save_project_as()
        try:
            save_project(self._project, self._project_file_path)
            self._last_save_state = self._project.to_dict()
            self._update_title()
            self._update_status()
            return True
        except Exception as e:
            QMessageBox.critical(self, "保存失败", str(e))
            return False

    def _save_project_as(self) -> bool:
        default_name = suggest_project_name(self._project.metadata.name)
        path, _ = QFileDialog.getSaveFileName(
            self, "保存 WavePack 工程", default_name, "WavePack 工程 (*.wpp)"
        )
        if not path:
            return False
        if not path.endswith(".wpp"):
            path += ".wpp"
        try:
            self._project_file_path = save_project(self._project, path)
            self._last_save_state = self._project.to_dict()
            self._update_title()
            self._update_status()
            return True
        except Exception as e:
            QMessageBox.critical(self, "保存失败", str(e))
            return False

    def _bind_project(self) -> None:
        self._metadata_panel.set_metadata(self._project.metadata)
        self._sample_panel.set_project(self._project)
        self._zone_list_panel.set_project(self._project)
        self._zone_editor.set_project(self._project)
        self._update_piano_roll()
        self._waveform_view.clear()

    def _maybe_save_dirty(self) -> bool:
        """若工程有未保存修改，询问是否保存；返回 False 表示取消操作。"""
        if not self._is_dirty():
            return True
        reply = QMessageBox.question(
            self,
            "未保存的更改",
            "当前工程有未保存的更改，是否保存？",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
        )
        if reply == QMessageBox.Save:
            return self._save_project()
        if reply == QMessageBox.Discard:
            return True
        return False

    def _is_dirty(self) -> bool:
        if self._last_save_state is None:
            return True
        return self._project.to_dict() != self._last_save_state

    def _update_title(self) -> None:
        name = self._project.metadata.name
        path = self._project_file_path or "未保存"
        dirty = "*" if self._is_dirty() else ""
        self.setWindowTitle(f"WavePack Maker - {name}{dirty} [{path}]")

    def _update_status(self) -> None:
        n_samples = len(self._project.samples)
        n_zones = len(self._project.zones)
        if self._project_file_path:
            self._project_label.setText(Path(self._project_file_path).name)
        else:
            self._project_label.setText("未保存")
        self._status_label.setText(f"采样: {n_samples}  Zone: {n_zones}")
        self._update_title()

    # ------------------------------------------------------------------
    # 交互回调
    # ------------------------------------------------------------------
    def _on_sample_selected(self, sample: Optional[SampleEntry]) -> None:
        if sample is not None:
            self._waveform_view.load_wav(sample.resolve_path())
        else:
            self._waveform_view.clear()

    def _on_zone_selected(self, zone: Optional[ZoneEntry]) -> None:
        self._zone_editor.set_zone(zone)
        if zone is not None:
            sample = self._project.get_sample(zone.sample_id)
            if sample is not None:
                self._waveform_view.load_wav(sample.resolve_path())
        self._update_piano_roll()

    def _on_zone_edited(self) -> None:
        self._zone_list_panel.refresh()
        self._update_piano_roll()
        self._update_status()

    def _on_play_sample(self, sample: SampleEntry) -> None:
        path = sample.resolve_path()
        if path.is_file():
            self._audio_player.play(path)

    def _on_apply_loop(self, start: int, end: int) -> None:
        # 实际区间从波形视图读取
        start, end = self._waveform_view.get_loop_region()
        zone = self._zone_editor.selected_zone() if hasattr(self._zone_editor, "selected_zone") else None
        # 更简单：更新当前 Zone 对应 Sample 的 loop
        current_zone = self._zone_list_panel.selected_zone()
        if current_zone is not None:
            sample = self._project.get_sample(current_zone.sample_id)
            if sample is not None:
                sample.loop_start = start
                sample.loop_end = end
                self._status_label.setText(f"已设置循环: {start} ~ {end}")

    def _update_piano_roll(self) -> None:
        zones = self._project.zones
        ranges = [(z.min_note, z.max_note) for z in zones]
        roots = [z.root_note for z in zones]
        self._piano_roll.set_highlight(ranges, roots)

    def _import_wav(self) -> None:
        self._sample_panel._on_import()

    def _export_wavepack(self) -> None:
        errs = self._project.validate()
        if errs:
            QMessageBox.warning(self, "导出前校验失败", "\n".join(errs))
            return

        default_name = f"{self._project.metadata.name}.wavepack"
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 .wavepack", default_name, "WavePack 文件 (*.wavepack)"
        )
        if not path:
            return
        if not path.endswith(".wavepack"):
            path += ".wavepack"

        try:
            builder = WavePackBuilder.from_project(self._project)
            builder.build(path)
            WavePackValidator(path).validate()
            QMessageBox.information(self, "导出成功", f"已导出: {path}")
        except ValidationError as e:
            QMessageBox.warning(self, "导出文件校验失败", "\n".join(e.messages))
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "关于 WavePack Maker",
            "<h2>WavePack Maker</h2>"
            "<p>面向 ESP32Synth 的专业音色打包/编辑上位机工具。</p>"
            "<p>工程文件后缀: .wpp<br>"
            "输出文件后缀: .wavepack</p>",
        )

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._maybe_save_dirty():
            event.accept()
        else:
            event.ignore()
