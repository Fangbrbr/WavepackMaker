"""WavePack Maker 主窗口。"""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStyle,
    QToolBar,
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
from .waveform_view import WaveformView
from .zone_editor import ZoneEditor
from .zone_list_panel import ZoneListPanel


class MainWindow(QMainWindow):
    """WavePack Maker 主界面。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("WavePack Maker")
        self.setMinimumSize(1400, 900)

        self._project = Project()
        self._project_file_path: Optional[str] = None
        self._last_save_state: Optional[dict] = None
        self._audio_player = AudioPlayer()
        self._ignore_dirty_once = True  # 首次新建工程不弹保存询问

        self._setup_menu()
        self._setup_toolbar()
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

        self._import_sample_action = QAction("导入 WAV 音源(&I)...", self)
        self._import_sample_action.triggered.connect(self._import_wav_samples)
        file_menu.addAction(self._import_sample_action)

        self._export_action = QAction("导出 .wavepack(&E)...", self)
        self._export_action.triggered.connect(self._export_wavepack)
        file_menu.addAction(self._export_action)

        file_menu.addSeparator()

        self._properties_action = QAction("工程属性(&P)...", self)
        self._properties_action.triggered.connect(self._edit_properties)
        file_menu.addAction(self._properties_action)

        self._exit_action = QAction("退出(&X)", self)
        self._exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self._exit_action.triggered.connect(self.close)
        file_menu.addAction(self._exit_action)

        help_menu = menu_bar.addMenu("帮助(&H)")
        self._about_action = QAction("关于(&A)", self)
        self._about_action.triggered.connect(self._show_about)
        help_menu.addAction(self._about_action)

    def _setup_toolbar(self) -> None:
        """顶部工具栏：左侧放常用工程操作，右侧放导出。"""
        toolbar = QToolBar("主工具栏", self)
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addToolBar(toolbar)

        # 左侧：新建工程
        new_btn = QAction(
            self.style().standardIcon(QStyle.SP_FileIcon), "新建工程", self
        )
        new_btn.setShortcut(QKeySequence.StandardKey.New)
        new_btn.triggered.connect(self._new_project)
        toolbar.addAction(new_btn)

        # 左侧：保存工程
        save_btn = QAction(
            self.style().standardIcon(QStyle.SP_DialogSaveButton), "保存工程", self
        )
        save_btn.setShortcut(QKeySequence.StandardKey.Save)
        save_btn.triggered.connect(self._save_project)
        toolbar.addAction(save_btn)

        # 左侧：工程属性
        props_btn = QAction(
            self.style().standardIcon(QStyle.SP_FileDialogInfoView), "工程属性", self
        )
        props_btn.triggered.connect(lambda: self._edit_properties("工程属性"))
        toolbar.addAction(props_btn)

        # 右侧：导出 wavepack（通过 stretch widget 靠右）
        export_btn = QAction(
            self.style().standardIcon(QStyle.SP_ArrowForward), "导出 .wavepack", self
        )
        export_btn.triggered.connect(self._export_wavepack)
        spacer = QWidget()
        spacer.setSizePolicy(
            self.sizePolicy().Expanding, self.sizePolicy().Preferred
        )
        toolbar.addWidget(spacer)
        toolbar.addAction(export_btn)

    def _setup_central(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)

        main_splitter = QSplitter(Qt.Vertical)
        main_layout.addWidget(main_splitter)

        # 上方面板：Zone 列表 | Zone 配置
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)

        top_splitter = QSplitter(Qt.Horizontal)
        top_layout.addWidget(top_splitter)

        self._zone_list_panel = ZoneListPanel()
        self._zone_list_panel.set_on_selection_changed(self._on_zone_selected)
        top_splitter.addWidget(self._zone_list_panel)

        self._zone_editor = ZoneEditor()
        self._zone_editor.set_on_changed(self._on_zone_edited)
        self._zone_editor.set_on_play(self._on_play_sample)
        self._zone_editor.set_on_set_loop(self._on_apply_loop)
        top_splitter.addWidget(self._zone_editor)

        # Zone 列表占更大空间，方便管理大量 Zone
        top_splitter.setSizes([850, 550])
        top_splitter.setStretchFactor(0, 3)
        top_splitter.setStretchFactor(1, 2)

        main_splitter.addWidget(top_widget)

        # 下方面板：波形预览 + 钢琴键
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(4)

        self._waveform_view = WaveformView()
        bottom_layout.addWidget(self._waveform_view, stretch=1)

        self._piano_roll = PianoRoll()
        self._piano_roll.note_clicked.connect(self._on_piano_key_clicked)
        bottom_layout.addWidget(self._piano_roll)

        main_splitter.addWidget(bottom_widget)
        # 上方配置区域更大，下方波形 + 钢琴键占剩余空间
        main_splitter.setSizes([520, 380])
        main_splitter.setStretchFactor(0, 2)
        main_splitter.setStretchFactor(1, 1)

    def _setup_statusbar(self) -> None:
        self._status_label = QLabel("就绪")
        self.statusBar().addWidget(self._status_label)
        self._project_label = QLabel("未保存")
        self.statusBar().addPermanentWidget(self._project_label)

    # ------------------------------------------------------------------
    # 工程生命周期
    # ------------------------------------------------------------------
    def _new_project(self) -> None:
        if self._ignore_dirty_once:
            self._ignore_dirty_once = False
        elif not self._maybe_save_dirty():
            return

        self._project = Project(metadata=ProjectMetadata())
        self._project_file_path = None
        self._last_save_state = self._project.to_dict()
        self._bind_project()
        self._update_title()
        self._update_status()
        # 主窗口显示后再延迟弹出新建工程对话框，避免界面未加载先弹窗
        QTimer.singleShot(300, lambda: self._edit_properties(title="新建工程"))

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
        self._zone_list_panel.set_project(self._project)
        self._zone_editor.set_project(self._project)
        self._zone_editor.set_zone(None)
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
        n_zones = len(self._project.zones)
        if self._project_file_path:
            self._project_label.setText(Path(self._project_file_path).name)
        else:
            self._project_label.setText("未保存")
        self._status_label.setText(f"Zone: {n_zones}")
        self._update_title()

    # ------------------------------------------------------------------
    # 交互回调
    # ------------------------------------------------------------------
    def _on_zone_selected(self, zone: Optional[ZoneEntry]) -> None:
        self._zone_editor.set_zone(zone)
        if zone is not None:
            sample = self._project.get_sample(zone.sample_id)
            if sample is not None:
                self._waveform_view.load_wav(sample.resolve_path())
            else:
                self._waveform_view.clear()
        else:
            self._waveform_view.clear()
        self._update_piano_roll()

    def _import_wav_samples(self) -> None:
        """通过文件菜单导入 WAV 音源到工程（供 Zone 选择使用）。"""
        paths, _ = QFileDialog.getOpenFileNames(
            self, "导入 WAV 音源", "", "WAV 文件 (*.wav)"
        )
        if not paths:
            return
        for path in paths:
            try:
                sample = SampleEntry.from_wav(path)
                self._project.add_sample(sample)
            except Exception as e:
                QMessageBox.warning(self, "导入失败", f"{path}\n{e}")
        # 刷新 Zone 列表的音源下拉框
        self._zone_list_panel.refresh()
        zone = self._zone_list_panel.selected_zone()
        if zone is not None:
            self._zone_editor.set_zone(zone)
        self._update_status()

    def _on_zone_edited(self) -> None:
        # Zone 参数变更后刷新列表中的汇总列
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
        zone = self._zone_list_panel.selected_zone()
        if zone is not None:
            sample = self._project.get_sample(zone.sample_id)
            if sample is not None:
                sample.loop_start = start
                sample.loop_end = end
                self._status_label.setText(f"已设置循环: {start} ~ {end}")

    def _update_piano_roll(self) -> None:
        zone = self._zone_editor._zone
        if zone is not None:
            self._piano_roll.set_highlight([(zone.min_note, zone.max_note)], [zone.root_note])
        else:
            self._piano_roll.clear_highlight()

    def _on_piano_key_clicked(self, note: int) -> None:
        """点击钢琴键：若 note 在当前 Zone 范围内则播放对应音源。"""
        zone = self._zone_editor._zone
        if zone is None:
            return
        if not (zone.min_note <= note <= zone.max_note):
            self._status_label.setText(f"Note {note} 不在当前 Zone 音域内")
            return
        sample = self._project.get_sample(zone.sample_id)
        if sample is not None:
            path = sample.resolve_path()
            if path.is_file():
                self._audio_player.play(path)
                self._status_label.setText(f"预览 Note {note}: {sample.name}")

    def _edit_properties(self, title: str = "工程属性") -> None:
        """弹出工程属性对话框编辑身份证元数据。"""
        from PySide6.QtWidgets import QDialogButtonBox

        snapshot = self._project.metadata.to_dict()

        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumWidth(500)
        layout = QVBoxLayout(dialog)

        panel = MetadataPanel()
        panel.set_metadata(self._project.metadata)
        layout.addWidget(panel)

        btns = QHBoxLayout()
        btns.addStretch()
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(dialog.accept)
        box.rejected.connect(dialog.reject)
        btns.addWidget(box)
        layout.addLayout(btns)

        if dialog.exec() == QDialog.Accepted:
            self._update_status()
        else:
            # 取消时恢复之前的元数据快照
            self._project.metadata = ProjectMetadata.from_dict(snapshot)
            self._update_status()

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
