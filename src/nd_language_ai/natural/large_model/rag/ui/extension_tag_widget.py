from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class ExtensionTagWidget(QWidget):
    changed = Signal()

    def __init__(self, initial_extensions: List[str]) -> None:
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(132)

        self._list = QListWidget()
        self._list.setObjectName("tagList")
        self._list.setFlow(QListView.Flow.LeftToRight)
        self._list.setResizeMode(QListView.ResizeMode.Adjust)
        self._list.setWrapping(True)
        self._list.setSpacing(6)
        self._list.setMinimumHeight(72)
        self._list.setMaximumHeight(72)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Add extension, e.g. .tex")
        self._add_button = QPushButton("Add")
        self._add_button.setObjectName("smallButton")
        self._remove_button = QPushButton("Remove selected")
        self._remove_button.setObjectName("smallButton")

        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(8)
        input_layout.addWidget(self._input, 1)
        input_layout.addWidget(self._add_button)
        input_layout.addWidget(self._remove_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(9)
        layout.addWidget(self._list)
        layout.addLayout(input_layout)

        self._add_button.clicked.connect(self._add_from_input)
        self._remove_button.clicked.connect(self._remove_selected)
        self._input.returnPressed.connect(self._add_from_input)
        self._list.itemDoubleClicked.connect(self._remove_item)

        for extension in initial_extensions:
            self.add_extension(extension, emit_signal=False)

    def extensions(self) -> List[str]:
        return [
            str(self._list.item(index).data(Qt.ItemDataRole.UserRole))
            for index in range(self._list.count())
        ]

    def add_extension(self, extension: str, emit_signal: bool = True) -> None:
        normalized = self._normalize(extension)
        if not normalized or normalized in self.extensions():
            return
        item = QListWidgetItem(normalized)
        item.setData(Qt.ItemDataRole.UserRole, normalized)
        self._list.addItem(item)
        if emit_signal:
            self.changed.emit()

    def _add_from_input(self) -> None:
        self.add_extension(self._input.text())
        self._input.clear()

    def _remove_selected(self) -> None:
        rows = sorted(
            {self._list.row(item) for item in self._list.selectedItems()},
            reverse=True,
        )
        if not rows:
            return
        for row in rows:
            self._list.takeItem(row)
        self.changed.emit()

    def _remove_item(self, item: QListWidgetItem) -> None:
        self._list.takeItem(self._list.row(item))
        self.changed.emit()

    def _normalize(self, extension: str) -> str:
        value = extension.strip().lower()
        if not value:
            return ""
        if not value.startswith("."):
            value = "." + value
        return value
