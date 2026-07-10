"""Zone 参数编辑器。"""

from typing import Callable, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..models import Project, SampleEntry, ZoneEntry
from .range_slider import RangeSlider


def _note_name(note: int) -> str:
    """返回 MIDI note 的音名，如 60 -> 'C4'。"""
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    return f"{names[note % 12]}{note // 12 - 1}"


class ZoneEditor(QGroupBox):
    """编辑单个 Zone 的所有参数，包括指定其音源采样。"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("Zone 配置", parent)
        self._project: Optional[Project] = None
        self._zone: Optional[ZoneEntry] = None
        self._on_changed: Optional[Callable[[], None]] = None
        self._on_play: Optional[Callable[[SampleEntry], None]] = None
        self._on_set_loop: Optional[Callable[[int, int], None]] = None
        self._on_crop: Optional[Callable[[int, int], None]] = None
        self._loading_zone = False
        self._setup_ui()
        # 初始不加载任何 Zone，但控件保持可用（避免显示为灰色禁用）
        self.set_zone(None)

    def set_theme(self, theme) -> None:
        """应用主题色到范围滑块与 Sustain 滑块。"""
        self._note_range_slider.set_theme(theme)
        self._vel_range_slider.set_theme(theme)
        accent = theme.accent.name()
        self._sustain_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 8px;
                background: #666666;
                border-radius: 4px;
            }}
            QSlider::sub-page:horizontal {{
                background: {accent};
                border-radius: 4px;
            }}
            QSlider::handle:horizontal {{
                background: {accent};
                width: 14px;
                margin: -3px 0;
                border-radius: 7px;
            }}
        """)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)

        self._name_edit = QLineEdit()
        self._name_edit.textChanged.connect(self._on_field_changed)

        self._sample_combo = QComboBox()
        self._sample_combo.currentIndexChanged.connect(self._on_sample_changed)

        # 采样根音（写入 .wavepack Sample Entry，供下位机计算播放速度基准）
        self._sample_root_spin = QSpinBox()
        self._sample_root_spin.setRange(0, 127)
        self._sample_root_spin.setToolTip("该 WAV 采样真实录制的 MIDI 音高，会写入二进制 Sample Entry")
        self._sample_root_spin.valueChanged.connect(self._on_sample_root_changed)

        # Note 范围：双头滑块 + 标签
        self._note_range_slider = RangeSlider(0, 127)
        self._note_range_slider.range_changed.connect(self._on_note_range_changed)
        self._note_range_label = QLabel("-")
        note_range_layout = QVBoxLayout()
        note_range_layout.addWidget(self._note_range_slider)
        note_range_layout.addWidget(self._note_range_label)

        # Velocity 范围：双头滑块 + 标签
        self._vel_range_slider = RangeSlider(0, 127)
        self._vel_range_slider.range_changed.connect(self._on_vel_range_changed)
        self._vel_range_label = QLabel("-")
        vel_range_layout = QVBoxLayout()
        vel_range_layout.addWidget(self._vel_range_slider)
        vel_range_layout.addWidget(self._vel_range_label)

        self._poly_mode_combo = QComboBox()
        self._poly_mode_combo.addItems(["retrigger", "multi", "legato"])
        self._poly_mode_combo.currentTextChanged.connect(self._on_field_changed)

        self._max_same_spin = QSpinBox()
        self._max_same_spin.setRange(1, 16)
        self._max_same_spin.valueChanged.connect(self._on_field_changed)

        self._pitch_spin = QSpinBox()
        self._pitch_spin.setRange(-100, 100)
        self._pitch_spin.valueChanged.connect(self._on_field_changed)

        # ADSR
        adsr_layout = QHBoxLayout()
        self._attack_spin = QSpinBox()
        self._attack_spin.setRange(0, 65535)
        self._attack_spin.setSuffix(" ms")
        self._decay_spin = QSpinBox()
        self._decay_spin.setRange(0, 65535)
        self._decay_spin.setSuffix(" ms")
        self._sustain_slider = QSlider(Qt.Horizontal)
        self._sustain_slider.setRange(0, 255)
        self._sustain_label = QLabel("0")
        self._sustain_slider.valueChanged.connect(self._on_sustain_changed)
        self._release_spin = QSpinBox()
        self._release_spin.setRange(0, 65535)
        self._release_spin.setSuffix(" ms")
        adsr_layout.addWidget(QLabel("A"))
        adsr_layout.addWidget(self._attack_spin)
        adsr_layout.addWidget(QLabel("D"))
        adsr_layout.addWidget(self._decay_spin)
        adsr_layout.addWidget(QLabel("S"))
        adsr_layout.addWidget(self._sustain_slider)
        adsr_layout.addWidget(self._sustain_label)
        adsr_layout.addWidget(QLabel("R"))
        adsr_layout.addWidget(self._release_spin)
        adsr_layout.addStretch()

        for spin in (self._attack_spin, self._decay_spin, self._release_spin):
            spin.valueChanged.connect(self._on_field_changed)

        self._flags_edit = QLineEdit()
        self._flags_edit.setReadOnly(True)
        self._flags_edit.setPlaceholderText("自动计算")

        self._validation_label = QLabel()
        self._validation_label.setStyleSheet("color: red;")
        self._validation_label.setWordWrap(True)

        form.addRow("名称:", self._name_edit)
        form.addRow("音源采样:", self._sample_combo)
        form.addRow("采样根音:", self._sample_root_spin)
        form.addRow("Note 范围:", note_range_layout)
        form.addRow("Velocity 范围:", vel_range_layout)
        form.addRow("复音模式:", self._poly_mode_combo)
        form.addRow("同音最大 Voice:", self._max_same_spin)
        form.addRow("音高微调 (cents):", self._pitch_spin)
        form.addRow("ADSR:", adsr_layout)
        form.addRow("最终 Flags:", self._flags_edit)
        form.addRow("校验:", self._validation_label)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        self._play_btn = QPushButton("▶ 播放音源")
        self._play_btn.clicked.connect(self._on_play_clicked)
        self._loop_btn = QPushButton("应用循环区间")
        self._loop_btn.setToolTip("将波形视图中框选的区间设为该 Zone 音源采样的 loop 范围")
        self._loop_btn.clicked.connect(self._on_loop_clicked)
        self._crop_btn = QPushButton("✂ 裁剪采样")
        self._crop_btn.setToolTip("Ctrl+左键/右键在波形视图中框选裁剪区后，点此按钮删除框选外的拖尾音")
        self._crop_btn.clicked.connect(self._on_crop_clicked)
        btn_layout.addWidget(self._play_btn)
        btn_layout.addWidget(self._loop_btn)
        btn_layout.addWidget(self._crop_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def set_project(self, project: Project) -> None:
        self._project = project
        self._refresh_sample_combo()

    def set_zone(self, zone: Optional[ZoneEntry]) -> None:
        self._zone = zone
        self._loading_zone = True
        if zone is None:
            # 清空表单但不禁用控件，避免灰色显示
            self.blockSignals(True)
            self._name_edit.clear()
            self._sample_combo.setCurrentIndex(-1)
            self._sample_root_spin.setValue(60)
            self._note_range_slider.set_range(0, 127)
            self._vel_range_slider.set_range(0, 127)
            self._poly_mode_combo.setCurrentText("retrigger")
            self._max_same_spin.setValue(1)
            self._pitch_spin.setValue(0)
            self._attack_spin.setValue(0)
            self._decay_spin.setValue(0)
            self._sustain_slider.setValue(255)
            self._sustain_label.setText("255")
            self._release_spin.setValue(0)
            self._flags_edit.clear()
            self._validation_label.clear()
            self._update_range_labels()
            self._loading_zone = False
            return

        self._name_edit.setText(zone.name)
        self._refresh_sample_combo()
        index = self._sample_combo.findData(zone.sample_id)
        if index >= 0:
            self._sample_combo.setCurrentIndex(index)
        sample = self._project.get_sample(zone.sample_id) if self._project else None
        self._sample_root_spin.setValue(sample.root_note if sample else 60)
        self._note_range_slider.set_range(zone.min_note, zone.max_note)
        self._vel_range_slider.set_range(zone.min_vel, zone.max_vel)
        self._poly_mode_combo.setCurrentText(zone.poly_mode)
        self._max_same_spin.setValue(zone.max_same_note_voices)
        self._pitch_spin.setValue(zone.pitch_cents)
        self._attack_spin.setValue(zone.adsr[0])
        self._decay_spin.setValue(zone.adsr[1])
        self._sustain_slider.setValue(zone.adsr[2])
        self._sustain_label.setText(str(zone.adsr[2]))
        self._release_spin.setValue(zone.adsr[3])
        self._update_range_labels()
        self._update_flags_and_validation()
        self._loading_zone = False

    def set_on_changed(self, callback: Callable[[], None]) -> None:
        self._on_changed = callback

    def set_on_play(self, callback: Callable[[SampleEntry], None]) -> None:
        self._on_play = callback

    def set_on_set_loop(self, callback: Callable[[int, int], None]) -> None:
        self._on_set_loop = callback

    def set_on_crop(self, callback: Callable[[int, int], None]) -> None:
        self._on_crop = callback

    def _refresh_sample_combo(self) -> None:
        self._sample_combo.clear()
        if self._project is None:
            return
        for sample in self._project.samples:
            self._sample_combo.addItem(sample.name, sample.id)

    def _on_sample_changed(self) -> None:
        if self._zone is None or self._loading_zone:
            return
        sample_id = self._sample_combo.currentData()
        if sample_id:
            self._zone.sample_id = sample_id
            sample = self._project.get_sample(sample_id) if self._project else None
            if sample is not None:
                self._sample_root_spin.blockSignals(True)
                self._sample_root_spin.setValue(sample.root_note)
                self._sample_root_spin.blockSignals(False)
        self._on_field_changed()

    def _on_sample_root_changed(self, value: int) -> None:
        if self._zone is None or self._loading_zone:
            return
        sample = self._project.get_sample(self._zone.sample_id) if self._project else None
        if sample is not None:
            sample.root_note = value
        self._on_field_changed()

    def _on_note_range_changed(self, low: int, high: int) -> None:
        if self._zone is None or self._loading_zone:
            return
        self._zone.min_note = low
        self._zone.max_note = high
        self._update_range_labels()
        self._on_field_changed()

    def _on_vel_range_changed(self, low: int, high: int) -> None:
        if self._zone is None or self._loading_zone:
            return
        self._zone.min_vel = low
        self._zone.max_vel = high
        self._update_range_labels()
        self._on_field_changed()

    def _update_range_labels(self) -> None:
        if self._zone is None:
            return
        self._note_range_label.setText(
            f"{_note_name(self._zone.min_note)} ({self._zone.min_note}) "
            f"~ {_note_name(self._zone.max_note)} ({self._zone.max_note})"
        )
        self._vel_range_label.setText(f"{self._zone.min_vel} ~ {self._zone.max_vel}")

    def _on_sustain_changed(self, value: int) -> None:
        self._sustain_label.setText(str(value))
        if self._loading_zone:
            return
        self._on_field_changed()

    def _on_field_changed(self) -> None:
        if self._zone is None or self._loading_zone:
            return
        self._zone.name = self._name_edit.text()
        self._zone.poly_mode = self._poly_mode_combo.currentText()
        self._zone.max_same_note_voices = self._max_same_spin.value()
        self._zone.pitch_cents = self._pitch_spin.value()
        self._zone.adsr = (
            self._attack_spin.value(),
            self._decay_spin.value(),
            self._sustain_slider.value(),
            self._release_spin.value(),
        )

        self._update_flags_and_validation()
        if self._on_changed:
            self._on_changed()

    def _update_flags_and_validation(self) -> None:
        if self._zone is None:
            return
        flags = self._zone.encoded_flags()
        self._flags_edit.setText(f"0x{flags:02X}")
        errs = self._zone.validate()
        if errs:
            self._validation_label.setText("\n".join(errs))
            self._validation_label.setStyleSheet("color: red;")
        else:
            self._validation_label.setText("OK")
            self._validation_label.setStyleSheet("color: green;")

    def _on_play_clicked(self) -> None:
        if self._zone is None or self._project is None or self._on_play is None:
            return
        sample = self._project.get_sample(self._zone.sample_id)
        if sample is not None:
            self._on_play(sample)

    def _on_loop_clicked(self) -> None:
        if self._on_set_loop is not None:
            self._on_set_loop(0, 0)

    def _on_crop_clicked(self) -> None:
        if self._on_crop is not None:
            self._on_crop(0, 0)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """点击面板空白处时移除输入焦点，触发当前输入框的编辑完成。"""
        self.setFocus()
        super().mousePressEvent(event)
