"""身份证元数据编辑面板。"""

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..models import ProjectMetadata


class MetadataPanel(QGroupBox):
    """编辑 ProjectMetadata 的表单面板。"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("身份证信息", parent)
        self._metadata: Optional[ProjectMetadata] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QFormLayout(self)
        layout.setLabelAlignment(Qt.AlignRight)

        self._name_edit = QLineEdit()
        self._version_edit = QLineEdit()
        self._author_edit = QLineEdit()
        self._copyright_edit = QLineEdit()
        self._category_edit = QLineEdit()
        self._tags_edit = QLineEdit()
        self._tags_edit.setPlaceholderText("用逗号分隔，如 piano, acoustic, grand")
        self._sample_rate_spin = QSpinBox()
        self._sample_rate_spin.setRange(8000, 192000)
        self._sample_rate_spin.setSingleStep(100)
        self._sample_rate_spin.setValue(44100)
        self._description_edit = QPlainTextEdit()
        self._description_edit.setMaximumHeight(60)
        self._notes_edit = QPlainTextEdit()
        self._notes_edit.setMaximumHeight(60)
        self._created_label = QLabel("-")
        self._updated_label = QLabel("-")

        layout.addRow("音色名称*:", self._name_edit)
        layout.addRow("工程版本:", self._version_edit)
        layout.addRow("作者:", self._author_edit)
        layout.addRow("版权:", self._copyright_edit)
        layout.addRow("分类:", self._category_edit)
        layout.addRow("标签:", self._tags_edit)
        layout.addRow("目标采样率*:", self._sample_rate_spin)
        layout.addRow("描述:", self._description_edit)
        layout.addRow("备注:", self._notes_edit)
        layout.addRow("创建时间:", self._created_label)
        layout.addRow("修改时间:", self._updated_label)

        # 绑定变更事件
        for widget in (
            self._name_edit,
            self._version_edit,
            self._author_edit,
            self._copyright_edit,
            self._category_edit,
            self._tags_edit,
        ):
            widget.textChanged.connect(self._on_changed)
        self._sample_rate_spin.valueChanged.connect(self._on_changed)
        self._description_edit.textChanged.connect(self._on_changed)
        self._notes_edit.textChanged.connect(self._on_changed)

    def _on_changed(self) -> None:
        if self._metadata is not None:
            self._metadata.name = self._name_edit.text() or "未命名音色"
            self._metadata.version = self._version_edit.text() or "1.0.0"
            self._metadata.author = self._author_edit.text()
            self._metadata.copyright = self._copyright_edit.text()
            self._metadata.category = self._category_edit.text()
            self._metadata.tags = [t.strip() for t in self._tags_edit.text().split(",") if t.strip()]
            self._metadata.sample_rate = self._sample_rate_spin.value()
            self._metadata.description = self._description_edit.toPlainText()
            self._metadata.notes = self._notes_edit.toPlainText()

    def set_metadata(self, metadata: ProjectMetadata) -> None:
        self._metadata = metadata
        self._name_edit.setText(metadata.name)
        self._version_edit.setText(metadata.version)
        self._author_edit.setText(metadata.author)
        self._copyright_edit.setText(metadata.copyright)
        self._category_edit.setText(metadata.category)
        self._tags_edit.setText(", ".join(metadata.tags))
        self._sample_rate_spin.setValue(metadata.sample_rate)
        self._description_edit.setPlainText(metadata.description)
        self._notes_edit.setPlainText(metadata.notes)
        self._created_label.setText(metadata.created_at)
        self._updated_label.setText(metadata.updated_at)
