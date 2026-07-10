"""工程属性编辑面板。"""

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent
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
        super().__init__("工程属性", parent)
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

    def apply_to_metadata(self, metadata: ProjectMetadata) -> None:
        """将当前表单内容写入 metadata 对象。"""
        metadata.name = self._name_edit.text() or "未命名音色"
        metadata.version = self._version_edit.text() or "1.0.0"
        metadata.author = self._author_edit.text()
        metadata.copyright = self._copyright_edit.text()
        metadata.category = self._category_edit.text()
        metadata.tags = [t.strip() for t in self._tags_edit.text().split(",") if t.strip()]
        metadata.sample_rate = self._sample_rate_spin.value()
        metadata.description = self._description_edit.toPlainText()
        metadata.notes = self._notes_edit.toPlainText()

    def set_metadata(self, metadata: ProjectMetadata) -> None:
        """将 metadata 对象加载到表单中显示。"""
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

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """点击面板空白处时移除输入焦点，触发当前输入框的编辑完成。"""
        self.setFocus()
        super().mousePressEvent(event)
