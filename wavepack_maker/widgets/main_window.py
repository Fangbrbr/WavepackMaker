"""WavePack Maker 主窗口。"""

import shutil
import sys
import wave
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStyle,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..audio_player import AudioPlayer
from ..builder import WavePackBuilder
from ..midi_input import MidiInput
from ..models import Project, ProjectMetadata, SampleEntry, ZoneEntry
from ..project_io import load_project, save_project, suggest_project_name
from ..validator import ValidationError, WavePackValidator
from .._version import __build_time__, __version__
from .metadata_panel import MetadataPanel
from .piano_roll import PianoRoll
from .sample_list_panel import SampleListPanel
from .theme import ThemeManager
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
        self._audio_player = AudioPlayer(self)
        self._midi_input = MidiInput(self)
        self._midi_input.note_on.connect(self._on_midi_note_on)
        self._ignore_dirty_once = True  # 首次新建工程不弹保存询问
        self._piano_window: Optional[QWidget] = None
        self._piano_roll_widget: Optional[PianoRoll] = None

        self._setup_menu()
        self._setup_toolbar()
        self._setup_central()
        self._setup_statusbar()
        self._new_project()
        self._setup_midi()

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

        # 左侧：打开工程
        open_btn = QAction(
            self.style().standardIcon(QStyle.SP_DirOpenIcon), "打开工程", self
        )
        open_btn.setShortcut(QKeySequence.StandardKey.Open)
        open_btn.triggered.connect(self._open_project)
        toolbar.addAction(open_btn)

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

        # 右侧：导入 WAV 采样
        import_btn = QAction(
            self.style().standardIcon(QStyle.SP_DialogOpenButton), "导入 WAV 采样", self
        )
        import_btn.triggered.connect(self._import_wav_samples)
        toolbar.addAction(import_btn)

        # 右侧：虚拟键盘（使用文字按钮，避免暗色图标在灰黑背景看不清）
        keyboard_btn = QAction("🎹 虚拟键盘", self)
        keyboard_btn.setToolTip("打开/关闭悬浮虚拟键盘")
        keyboard_btn.triggered.connect(self._toggle_piano_keyboard)
        toolbar.addAction(keyboard_btn)

        # 右侧：导出 wavepack（通过 stretch widget 靠右）
        export_btn = QAction(
            self.style().standardIcon(QStyle.SP_ArrowForward), "导出 .wavepack", self
        )
        export_btn.triggered.connect(self._export_wavepack)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)
        toolbar.addAction(export_btn)

    def _setup_central(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)

        main_splitter = QSplitter(Qt.Vertical)
        main_layout.addWidget(main_splitter)

        # 上方面板：采样清单 | Zone 列表 | Zone 配置
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)

        top_splitter = QSplitter(Qt.Horizontal)
        top_layout.addWidget(top_splitter)

        self._sample_panel = SampleListPanel()
        self._sample_panel.set_on_selection_changed(self._on_sample_selected)
        self._sample_panel.import_requested.connect(self._import_wav_samples)
        self._sample_panel.delete_requested.connect(self._on_delete_sample)
        top_splitter.addWidget(self._sample_panel)

        self._zone_list_panel = ZoneListPanel()
        self._zone_list_panel.set_on_selection_changed(self._on_zone_selected)
        top_splitter.addWidget(self._zone_list_panel)

        self._zone_editor = ZoneEditor()
        self._zone_editor.set_on_changed(self._on_zone_edited)
        self._zone_editor.set_on_play(self._on_play_sample)
        self._zone_editor.set_on_set_loop(self._on_apply_loop)
        self._zone_editor.set_on_crop(self._on_crop_sample)
        top_splitter.addWidget(self._zone_editor)

        # 采样清单较窄，Zone 列表和配置占主要空间
        top_splitter.setSizes([160, 640, 500])
        top_splitter.setStretchFactor(0, 0)
        top_splitter.setStretchFactor(1, 3)
        top_splitter.setStretchFactor(2, 2)

        main_splitter.addWidget(top_widget)

        # 下方面板：波形预览
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        self._waveform_view = WaveformView()
        self._waveform_view.loop_changed.connect(self._on_loop_changed)
        bottom_layout.addWidget(self._waveform_view, stretch=1)

        main_splitter.addWidget(bottom_widget)
        # 上方配置区域更大，下方波形占剩余空间
        main_splitter.setSizes([520, 380])
        main_splitter.setStretchFactor(0, 2)
        main_splitter.setStretchFactor(1, 1)

    def _setup_statusbar(self) -> None:
        self._status_label = QLabel("就绪")
        self.statusBar().addWidget(self._status_label)
        self._project_label = QLabel("未保存")
        self.statusBar().addPermanentWidget(self._project_label)

    def set_theme(self, theme: ThemeManager) -> None:
        """应用主题色到各子控件。"""
        self._theme = theme
        self._waveform_view.set_theme(theme)
        self._zone_editor.set_theme(theme)
        self._sample_panel.set_theme(theme.accent.name())
        self._zone_list_panel.set_theme(theme.accent.name())
        if self._piano_window is not None and self._piano_roll_widget is not None:
            self._piano_roll_widget.set_theme(theme)

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
            self._ensure_project_dirs()
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
            self._ensure_project_dirs()
            self._last_save_state = self._project.to_dict()
            self._update_title()
            self._update_status()
            return True
        except Exception as e:
            QMessageBox.critical(self, "保存失败", str(e))
            return False

    def _ensure_project_dirs(self) -> None:
        """确保工程目录下存在 samples/ 和 output/ 子目录。"""
        if self._project_file_path is None:
            return
        project_dir = Path(self._project_file_path).parent
        (project_dir / "samples").mkdir(parents=True, exist_ok=True)
        (project_dir / "output").mkdir(parents=True, exist_ok=True)

    def _bind_project(self) -> None:
        project_dir = Path(self._project_file_path).parent if self._project_file_path else None
        self._project.sync_samples_with_directory(project_dir)
        self._sample_panel.set_project(self._project)
        self._zone_list_panel.set_project(self._project)
        self._zone_editor.set_project(self._project)

        # 自动选中第一个采样
        if self._project.samples:
            first_sample = self._project.samples[0]
            self._sample_panel.select_sample(first_sample.id)
        else:
            self._waveform_view.clear()

        # 自动选中第一个 Zone
        if self._project.zones:
            first_zone = self._project.zones[0]
            self._zone_list_panel._select_zone(first_zone.id)
            self._zone_editor.set_zone(first_zone)
        else:
            self._zone_editor.set_zone(None)

        self._update_piano_roll()

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
    def _on_sample_selected(self, sample: Optional[SampleEntry]) -> None:
        """点击采样清单时，在波形预览中显示该采样并允许编辑循环标记。"""
        project_dir = Path(self._project_file_path).parent if self._project_file_path else None
        if sample is not None:
            self._waveform_view.load_wav(sample.resolve_path(project_dir))
            self._waveform_view.set_loop_region(sample.loop_start, sample.loop_end)
            self._waveform_view.set_editable(True)
            self._zone_list_panel.set_current_sample_id(sample.id)
        else:
            self._waveform_view.clear()
            self._waveform_view.set_editable(False)
            self._zone_list_panel.set_current_sample_id(None)

    def _on_zone_selected(self, zone: Optional[ZoneEntry]) -> None:
        project_dir = Path(self._project_file_path).parent if self._project_file_path else None
        self._zone_editor.set_zone(zone)
        if zone is not None:
            sample = self._project.get_sample(zone.sample_id)
            if sample is not None:
                self._waveform_view.load_wav(sample.resolve_path(project_dir))
                self._waveform_view.set_loop_region(sample.loop_start, sample.loop_end)
                self._waveform_view.set_editable(False)
                self._sample_panel.select_sample(sample.id)
            else:
                self._waveform_view.clear()
                self._waveform_view.set_editable(False)
        else:
            self._waveform_view.clear()
            self._waveform_view.set_editable(False)
        self._update_piano_roll()

    def _import_wav_samples(self) -> None:
        """导入 WAV 音源并自动复制到工程目录下的 samples/ 文件夹。"""
        # 若工程未保存，需要先保存工程以确定采样存放目录
        if self._project_file_path is None:
            reply = QMessageBox.information(
                self,
                "需要先保存工程",
                "导入 WAV 前需要先保存工程文件，以便将采样存放到工程目录下的 samples/ 文件夹。\n\n"
                "点击“确定”后选择工程保存位置。",
                QMessageBox.Ok | QMessageBox.Cancel,
            )
            if reply != QMessageBox.Ok:
                return
            if not self._save_project_as():
                return

        project_dir = Path(self._project_file_path).parent
        samples_dir = project_dir / "samples"
        samples_dir.mkdir(parents=True, exist_ok=True)

        paths, _ = QFileDialog.getOpenFileNames(
            self, "导入 WAV 音源", "", "WAV 文件 (*.wav)"
        )
        if not paths:
            return

        copied = 0
        skipped = 0
        for path in paths:
            src = Path(path)
            dst = samples_dir / src.name
            # 若已存在同名文件，询问是否覆盖
            if dst.exists():
                reply = QMessageBox.question(
                    self,
                    "采样已存在",
                    f"文件 \"{src.name}\" 已经在工程中存在，是否覆盖？",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if reply != QMessageBox.Yes:
                    skipped += 1
                    continue
            try:
                shutil.copy2(src, dst)
                copied += 1
            except Exception as e:
                QMessageBox.warning(self, "导入失败", f"{path}\n{e}")

        if copied:
            self._project.sync_samples_with_directory(project_dir)
            self._last_save_state = self._project.to_dict()
            self._update_title()
            self._update_status()
            # 刷新采样清单与 Zone 列表
            self._sample_panel.refresh()
            self._zone_list_panel.refresh()
            zone = self._zone_list_panel.selected_zone()
            if zone is not None:
                self._zone_editor.set_zone(zone)
        self._status_label.setText(f"已导入 {copied} 个，跳过 {skipped} 个")

    def _on_delete_sample(self, sample: SampleEntry) -> None:
        """删除采样：从工程中移除并删除 samples/ 目录下的真实文件。"""
        if self._project is None:
            return

        project_dir = Path(self._project_file_path).parent if self._project_file_path else None
        wav_path = sample.resolve_path(project_dir)

        # 删除工程模型中的采样及其引用的 Zone
        self._project.remove_sample(sample.id)

        # 删除真实文件
        if wav_path.is_file():
            try:
                wav_path.unlink()
            except Exception as e:
                QMessageBox.warning(self, "删除文件失败", f"{wav_path}\n{e}")

        self._sample_panel.refresh()
        self._zone_list_panel.refresh()
        self._zone_editor.set_zone(self._zone_list_panel.selected_zone())
        self._update_status()
        self._status_label.setText(f"已删除采样: {sample.name}")

    def _on_zone_edited(self) -> None:
        # Zone 参数变更后刷新列表中的汇总列
        self._zone_list_panel.refresh()
        self._update_piano_roll()
        self._update_status()

    def _on_play_sample(self, sample: SampleEntry) -> None:
        project_dir = Path(self._project_file_path).parent if self._project_file_path else None
        path = sample.resolve_path(project_dir)
        if path.is_file():
            self._audio_player.play(path)

    def _on_loop_changed(self, start: int, end: int) -> None:
        """波形视图拖动循环光标时，同步到当前 WAV 采样。"""
        sample = self._sample_panel.selected_sample()
        if sample is None:
            return
        sample.loop_start = start
        sample.loop_end = end
        self._status_label.setText(f"循环区间: {start} ~ {end}")

    def _on_apply_loop(self, start: int, end: int) -> None:
        """应用循环区间按钮：将波形视图当前框选区间写入采样。"""
        start, end = self._waveform_view.get_loop_region()
        self._on_loop_changed(start, end)

    def _on_crop_sample(self, start: int, end: int) -> None:
        """根据波形视图的裁剪区，删除采样框选外的数据以减小体积。"""
        sample = self._sample_panel.selected_sample()
        if sample is None:
            return
        project_dir = Path(self._project_file_path).parent if self._project_file_path else None
        path = sample.resolve_path(project_dir)
        if not path.is_file():
            QMessageBox.warning(self, "裁剪失败", "采样文件不存在")
            return

        start, end = self._waveform_view.get_trim_region()
        if end <= start:
            QMessageBox.information(self, "裁剪", "请先框选有效的裁剪区域（Ctrl+左键/右键）")
            return

        reply = QMessageBox.question(
            self,
            "裁剪采样",
            f"确定裁剪采样 \"{sample.name}\" 吗？\n"
            f"将保留 frame {start} ~ {end} 之间的数据，其余部分永久删除。",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            with wave.open(str(path), "rb") as wf:
                nch = wf.getnchannels()
                sw = wf.getsampwidth()
                sr = wf.getframerate()
                nframes = wf.getnframes()
                start = max(0, min(start, nframes))
                end = max(start, min(end, nframes))
                wf.setpos(start)
                raw = wf.readframes(end - start)

            with wave.open(str(path), "wb") as wf:
                wf.setnchannels(nch)
                wf.setsampwidth(sw)
                wf.setframerate(sr)
                wf.writeframes(raw)

            # 更新 SampleEntry 元数据与 loop 标记
            sample.nframes = end - start
            sample.sample_rate = sr
            sample.channels = nch
            sample.bits = sw * 8
            if sample.loop_start >= sample.nframes or sample.loop_end > sample.nframes:
                sample.loop_start = 0
                sample.loop_end = sample.nframes

            # 刷新 UI
            self._waveform_view.load_wav(path)
            self._waveform_view.set_loop_region(sample.loop_start, sample.loop_end)
            self._waveform_view.set_trim_region(0, sample.nframes)
            self._sample_panel.refresh()
            self._zone_list_panel.refresh()
            self._last_save_state = self._project.to_dict()
            self._update_title()
            self._update_status()
            self._status_label.setText(f"已裁剪采样: {sample.name} ({start}~{end})")
        except Exception as e:
            QMessageBox.critical(self, "裁剪失败", str(e))

    def _update_piano_roll(self) -> None:
        widget = self._piano_roll_widget
        if widget is None:
            return
        if self._project is not None and self._project.zones:
            ranges = []
            roots = []
            for z in self._project.zones:
                sample = self._project.get_sample(z.sample_id)
                if sample is not None:
                    ranges.append((z.min_note, z.max_note))
                    roots.append(sample.root_note)
            widget.set_highlight(ranges, roots)
        else:
            widget.clear_highlight()

    def _on_piano_key_clicked(self, note: int) -> None:
        """点击钢琴键：通过 MIDI 引擎触发 NOTE_ON。"""
        self._on_midi_note_on(note)

    def _on_midi_note_on(self, note: int, velocity: int = 127) -> None:
        """MIDI 引擎：触发 NOTE_ON，并在钢琴卷帘上显示按下状态。"""
        if self._piano_roll_widget is not None:
            self._piano_roll_widget.press_note(note)
        self._play_note(note, velocity)

    def _play_note(self, note: int, velocity: int = 127) -> None:
        """根据所有 Zone 的 note 映射播放指定 note，并按根音差计算音高。"""
        if self._project is None:
            return
        project_dir = Path(self._project_file_path).parent if self._project_file_path else None
        # 找到覆盖该 note 的第一个 Zone（按Zone列表顺序）
        for zone in self._project.zones:
            if zone.min_note <= note <= zone.max_note:
                sample = self._project.get_sample(zone.sample_id)
                if sample is not None:
                    path = sample.resolve_path(project_dir)
                    if path.is_file():
                        # 以 sample.root_note 为基准，按半音差计算播放速率
                        # 1 半音 = 100 cents，rate = 2^(cents/1200)
                        semitones = note - sample.root_note
                        cents = semitones * 100 + zone.pitch_cents
                        rate = 2.0 ** (cents / 1200.0)
                        self._audio_player.play(path, rate)
                        self._status_label.setText(
                            f"预览 Note {note} (vel={velocity}): {sample.name} "
                            f"[{zone.name or zone.id}] rate={rate:.3f}"
                        )
                        return
        self._status_label.setText(f"Note {note} 未映射到任何 Zone")

    def _setup_midi(self) -> None:
        """尝试打开第一个可用的 MIDI 输入设备。"""
        ports = self._midi_input.available_ports()
        if ports:
            if self._midi_input.open(0):
                self._status_label.setText(f"MIDI 已连接: {ports[0]}")

    def _toggle_piano_keyboard(self) -> None:
        """显示/隐藏悬浮虚拟键盘窗口。"""
        if self._piano_window is None:
            self._piano_window = QWidget(self, Qt.Tool | Qt.WindowStaysOnTopHint)
            self._piano_window.setWindowTitle("虚拟键盘")
            self._piano_window.setMinimumWidth(800)
            self._piano_window.setMinimumHeight(120)
            layout = QVBoxLayout(self._piano_window)
            layout.setContentsMargins(4, 4, 4, 4)
            self._piano_roll_widget = PianoRoll()
            self._piano_roll_widget.set_theme(self._theme)
            self._piano_roll_widget.note_clicked.connect(self._on_piano_key_clicked)
            layout.addWidget(self._piano_roll_widget)
            # 初始高亮所有 Zone
            if self._project is not None and self._project.zones:
                ranges = []
                roots = []
                for z in self._project.zones:
                    sample = self._project.get_sample(z.sample_id)
                    if sample is not None:
                        ranges.append((z.min_note, z.max_note))
                        roots.append(sample.root_note)
                self._piano_roll_widget.set_highlight(ranges, roots)
            self._piano_window.show()
        else:
            if self._piano_window.isVisible():
                self._piano_window.hide()
            else:
                self._piano_window.show()

    def _edit_properties(self, title: str = "工程属性") -> None:
        """弹出工程属性对话框编辑工程元数据。"""
        from PySide6.QtWidgets import QDialogButtonBox

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
            panel.apply_to_metadata(self._project.metadata)
            self._project.metadata.touch_updated()
            self._last_save_state = self._project.to_dict()
            self._update_status()

    def _export_wavepack(self) -> None:
        errs = self._project.validate()
        if errs:
            QMessageBox.warning(self, "导出前校验失败", "\n".join(errs))
            return

        # 默认导出路径：工程目录/output/音色名.wavepack
        default_name = f"{self._project.metadata.name}.wavepack"
        if self._project_file_path is not None:
            default_path = str(Path(self._project_file_path).parent / "output" / default_name)
        else:
            default_path = default_name
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 .wavepack", default_path, "WavePack 文件 (*.wavepack)"
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
        """弹出自定义 About 对话框，预留 Logo 框，文字大气居中/对齐。"""
        dialog = QDialog(self)
        dialog.setWindowTitle("关于 WavePack Maker")
        dialog.setMinimumWidth(420)
        dialog.setMaximumWidth(520)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setAlignment(Qt.AlignCenter)

        # Logo
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            base_path = Path(sys._MEIPASS)
        else:
            base_path = Path(__file__).resolve().parent.parent.parent

        logo_label = QLabel()
        logo_label.setFixedSize(120, 120)
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setStyleSheet(
            "QLabel { border: 2px dashed #888888; border-radius: 12px; background-color: #3a3a3a; color: #888888; font-size: 14px; }"
        )
        logo_path = base_path / "assets" / "logo.png"
        if logo_path.is_file():
            pixmap = QPixmap(str(logo_path)).scaled(
                112, 112, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            logo_label.setPixmap(pixmap)
        else:
            logo_label.setText("LOGO")
        layout.addWidget(logo_label, alignment=Qt.AlignCenter)

        # 标题
        title = QLabel("WavePack Maker")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #ffffff;")
        layout.addWidget(title)

        # 副标题
        subtitle = QLabel("面向 ESP32Synth 的专业音色打包/编辑上位机工具")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("font-size: 12px; color: #aaaaaa;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # 信息网格（多列分别对齐，标题列:信息列 = 1:2）
        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 2)

        info_items = [
            ("版本", __version__),
            ("编译时间", __build_time__[:19].replace("T", " ") + " UTC"),
            ("作者", "Fmil"),
            ("邮箱", "fmil123@qq.com"),
        ]
        for row, (label, value) in enumerate(info_items):
            lbl = QLabel(f"{label}:")
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            lbl.setStyleSheet("color: #cccccc;")
            val = QLabel(value)
            val.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            val.setStyleSheet("color: #ffffff;")
            if label == "邮箱":
                val.setText("<a href=\"mailto:fmil123@qq.com\" style=\"color: #4dabf7;\">fmil123@qq.com</a>")
                val.setOpenExternalLinks(True)
            grid.addWidget(lbl, row, 0)
            grid.addWidget(val, row, 1)
        layout.addLayout(grid)

        layout.addStretch()

        # 确定按钮
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok)
        btn_box.accepted.connect(dialog.accept)
        layout.addWidget(btn_box, alignment=Qt.AlignCenter)

        dialog.exec()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        """未在输入控件内时，键盘按键直接触发 MIDI note 预览。"""
        focus = self.focusWidget()
        if isinstance(focus, (QLineEdit, QPlainTextEdit, QSpinBox, QComboBox)):
            super().keyPressEvent(event)
            return

        key_to_note = {
            # 低音八度
            ord("Z"): 48, ord("S"): 49, ord("X"): 50, ord("D"): 51,
            ord("C"): 52, ord("V"): 53, ord("G"): 54, ord("B"): 55,
            ord("H"): 56, ord("N"): 57, ord("J"): 58, ord("M"): 59,
            # 中音八度
            ord("Q"): 60, ord("2"): 61, ord("W"): 62, ord("3"): 63,
            ord("E"): 64, ord("R"): 65, ord("5"): 66, ord("T"): 67,
            ord("6"): 68, ord("Y"): 69, ord("7"): 70, ord("U"): 71,
            # 高音八度
            ord("I"): 72, ord("9"): 73, ord("O"): 74, ord("0"): 75,
            ord("P"): 76,
        }
        note = key_to_note.get(event.key())
        if note is not None:
            self._on_piano_key_clicked(note)
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._maybe_save_dirty():
            event.accept()
        else:
            event.ignore()
