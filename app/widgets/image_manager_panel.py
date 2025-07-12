# app/widgets/image_manager_panel.py
from PyQt5.QtWidgets import (QAbstractItemView, QFileDialog, QGroupBox,
                             QHBoxLayout, QListWidget, QMessageBox,
                             QPushButton, QVBoxLayout, QWidget)
from PyQt5.QtCore import pyqtSignal
from typing import List

class ImageManagerPanel(QWidget):
    """画像リストの管理と操作を行うパネル"""
    imageListChanged = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_paths = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        group = QGroupBox("画像管理")
        group_layout = QVBoxLayout()
        
        btn_layout = QHBoxLayout()
        btn_add = QPushButton("追加")
        btn_add.clicked.connect(self.add_images)
        btn_reset = QPushButton("リセット")
        btn_reset.clicked.connect(self.reset_images)
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_reset)
        group_layout.addLayout(btn_layout)

        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(QAbstractItemView.InternalMove)
        self.list_widget.model().rowsMoved.connect(self._on_list_changed)
        group_layout.addWidget(self.list_widget)

        group.setLayout(group_layout)
        layout.addWidget(group)

    def add_images(self):
        files, _ = QFileDialog.getOpenFileNames(self, "画像を選択", "", "画像ファイル (*.png *.jpg *.jpeg *.tif *.tiff *.bmp)")
        if files:
            self.list_widget.addItems(files)
            self._on_list_changed()
    
    def set_image_paths(self, paths: List[str]):
        self.list_widget.clear()
        self.list_widget.addItems(paths)
        self._on_list_changed()

    def reset_images(self):
        reply = QMessageBox.question(self, "確認", "全ての画像を一括で削除しますか？",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.list_widget.clear()
            self._on_list_changed()
    
    def _on_list_changed(self):
        self.image_paths = [self.list_widget.item(i).text() for i in range(self.list_widget.count())]
        self.imageListChanged.emit(self.image_paths)
    
    def get_image_paths(self) -> List[str]:
        return self.image_paths
