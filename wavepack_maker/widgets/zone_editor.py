"""采样配置编辑器（底层对应一个 Zone）。"""

from typing import Callable, List, Optional

from PySide6.QtCore import Qt
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


class ZoneEditor(QGroupBox):
    """编辑单个采样对应的 Zone 参数。"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("采样配置", parent)
        self._project: Optional[Project] = None
        self._zone: Optional[ZoneEntry] = None
        self._on_changed: Optional[Callable[[], None]] = None
        self._on_play: Optional[Callable[[SampleEntry], None]] = None
        self._on_set_loop: Optional[Callable[[int, int], None]] = None
        self._setup_ui()
        self.setEnabled(False)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)

        self._name_edit = QLineEdit()
        self._name_edit.textChanged.connect(self._on_field_changed)

        self._sample_label = QLabel("-")

        self._root_spin = QSpinBox()
        self._root_spin.setRange(0, 127)
        self._root_spin.valueChanged.connect(self._on_field_changed)

        self._min_note_spin = QSpinBox()
        self._min_note_spin.setRange(0, 127)
        self._min_note_spin.valueChanged.connect(self._on_field_changed)

        self._max_note_spin = QSpinBox()
        self._max_note_spin.setRange(0, 127)
        self._max_note_spin.valueChanged.connect(self._on_field_changed)

        self._min_vel_spin = QSpinBox()
        self._min_vel_spin.setRange(0, 127)
        self._min_vel_spin.valueChanged.connect(self._on_field_changed)

        self._max_vel_spin = QSpinBox()
        self._max_vel_spin.setRange(0, 127)
        self._max_vel_spin.valueChanged.connect(self._on_field_changed)

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
        form.addRow("关联采样:", self._sample_label)
        form.addRow("根音 (Root):", self._root_spin)
        form.addRow("最低 Note:", self._min_note_spin)
        form.addRow("最高 Note:", self._max_note_spin)
        form.addRow("最小 Velocity:", self._min_vel_spin)
        form.addRow("最大 Velocity:", self._max_vel_spin)
        form.addRow("复音模式:", self._poly_mode_combo)
        form.addRow("同音最大 Voice:", self._max_same_spin)
        form.addRow("音高微调 (cents):", self._pitch_spin)
        form.addRow("ADSR:", adsr_layout)
        form.addRow("最终 Flags:", self._flags_edit)
        form.addRow("校验:", self._validation_label)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        self._play_btn = QPushButton("▶ 播放采样")
        self._play_btn.clicked.connect(self._on_play_clicked)
        self._loop_btn = QPushButton("应用循环区间")
        self._loop_btn.setToolTip("将波形视图中框选的区间设为该采样的 loop 范围")
        self._loop_btn.clicked.connect(self._on_loop_clicked)
        btn_layout.addWidget(self._play_btn)
        btn_layout.addWidget(self._loop_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def set_project(self, project: Project) -> None:
        self._project = project

    def set_zone(self, zone: Optional[ZoneEntry]) -> None:
        self._zone = zone
        self.setEnabled(zone is not None)
        if zone is None:
            self._sample_label.setText("-")
            return

        self.blockSignals(True)
        self._name_edit.setText(zone.name)
        sample = self._project.get_sample(zone.sample_id) if self._project else None
        self._sample_label.setText(sample.name if sample else "-")
        self._root_spin.setValue(zone.root_note)
        self._min_note_spin.setValue(zone.min_note)
        self._max_note_spin.setValue(zone.max_note)
        self._min_vel_spin.setValue(zone.min_vel)
        self._max_vel_spin.setValue(zone.max_vel)
        self._poly_mode_combo.setCurrentText(zone.poly_mode)
        self._max_same_spin.setValue(zone.max_same_note_voices)
        self._pitch_spin.setValue(zone.pitch_cents)
        self._attack_spin.setValue(zone.adsr[0])
        self._decay_spin.setValue(zone.adsr[1])
        self._sustain_slider.setValue(zone.adsr[2])
        self._sustain_label.setText(str(zone.adsr[2]))
        self._release_spin.setValue(zone.adsr[3])
        self.blockSignals(False)

        self._update_flags_and_validation()

    def set_on_changed(self, callback: Callable[[], None]) -> None:
        self._on_changed = callback

    def set_on_play(self, callback: Callable[[SampleEntry], None]) -> None:
        self._on_play = callback

    def set_on_set_loop(self, callback: Callable[[int, int], None]) -> None:
        self._on_set_loop = callback

    def _on_sustain_changed(self, value: int) -> None:
        self._sustain_label.setText(str(value))
        self._on_field_changed()

    def _on_field_changed(self) -> None:
        if self._zone is None:
            return
        self._zone.name = self._name_edit.text()
        self._zone.root_note = self._root_spin.value()
        self._zone.min_note = self._min_note_spin.value()
        self._zone.max_note = self._max_note_spin.value()
        self._zone.min_vel = self._min_vel_spin.value()
        self._zone.max_vel = self._max_vel_spin.value()
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
