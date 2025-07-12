# app/main_window.py
import logging
import os
from typing import Any, List

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QDragEnterEvent, QDropEvent
from PyQt5.QtWidgets import (QFileDialog, QHBoxLayout, QMainWindow,
                             QMessageBox, QProgressDialog, QPushButton,
                             QSplitter, QVBoxLayout, QWidget)

from app.core.pdf_generator import PDFGenerationThread
from app.core.settings import GridSettings, SETTINGS_FILE
from app.widgets.image_manager_panel import ImageManagerPanel
from app.widgets.preview_panel import PreviewPanel
from app.widgets.settings_panel import SettingsPanel

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ImageGridApp(QMainWindow):
    """アプリケーションのメインウィンドウ"""

    def __init__(self):
        super().__init__()
        self.settings = GridSettings.load_from_file(SETTINGS_FILE)
        self.image_paths: List[str] = []
        self.pdf_thread: PDFGenerationThread = None
        
        self.init_ui()
        self.setWindowTitle("画像グリッド作成ツール")
        self.resize(1200, 800)

    def init_ui(self):
        self._init_menubar()
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        splitter = QSplitter(Qt.Horizontal)
        
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        self.image_manager_panel = ImageManagerPanel()
        self.settings_panel = SettingsPanel(self.settings)
        left_layout.addWidget(self.image_manager_panel)
        left_layout.addWidget(self.settings_panel)
        
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        self.preview_panel = PreviewPanel(self.settings)
        btn_generate_pdf = QPushButton("PDFを作成")
        btn_generate_pdf.setFixedHeight(40)
        right_layout.addWidget(self.preview_panel)
        right_layout.addWidget(btn_generate_pdf)
        
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        main_layout.addWidget(splitter)
        
        self.setAcceptDrops(True)
        self._connect_signals()

    def _init_menubar(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("ファイル")
        load_action = file_menu.addAction("設定を読み込む...")
        load_action.triggered.connect(self.load_settings_file)
        save_as_action = file_menu.addAction("設定を名前を付けて保存...")
        save_as_action.triggered.connect(self.save_settings_as)
        file_menu.addSeparator()
        exit_action = file_menu.addAction("終了")
        exit_action.triggered.connect(self.close)
        
        edit_menu = menubar.addMenu("編集")
        reset_settings_action = edit_menu.addAction("設定をデフォルトにリセット")
        reset_settings_action.triggered.connect(self.reset_settings_to_default)

    def _connect_signals(self):
        self.image_manager_panel.imageListChanged.connect(self.on_image_list_changed)
        self.settings_panel.settingsChanged.connect(self.preview_panel.on_settings_updated)
        self.findChild(QPushButton, None, Qt.FindChildrenRecursively).clicked.connect(self.generate_pdf)

    def on_image_list_changed(self, new_image_paths: List[str]):
        self.image_paths = new_image_paths
        self.preview_panel.update_preview(self.image_paths)

    def load_settings_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "設定ファイルを開く", "", "JSON Files (*.json)")
        if path:
            self.settings = GridSettings.load_from_file(path)
            self.settings_panel.settings = self.settings
            self.settings_panel.update_ui_from_settings()
            self.preview_panel.settings = self.settings
            logger.info(f"{path} から設定を読み込みました。")
    
    def save_settings_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "設定ファイルを保存", "", "PDF Files (*.pdf)")
        if path:
            if not path.lower().endswith('.json'):
                path += '.json'
            self.settings.save_to_file(path)

    def reset_settings_to_default(self):
        reply = QMessageBox.question(self, "確認", "全ての設定を初期状態に戻しますか？", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.settings = GridSettings()
            self.settings_panel.settings = self.settings
            self.settings_panel.update_ui_from_settings()
            self.preview_panel.settings = self.settings
            logger.info("設定をデフォルトにリセットしました。")

    def generate_pdf(self):
        if not self.image_paths:
            QMessageBox.warning(self, "警告", "画像が追加されていません。"); return
        save_path, _ = QFileDialog.getSaveFileName(self, "PDFを保存", "output.pdf", "PDF Files (*.pdf)")
        if not save_path: return

        self.progress_dialog = QProgressDialog("PDFを生成中...", "キャンセル", 0, 100, self)
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        
        self.pdf_thread = PDFGenerationThread(self.image_paths, self.settings)
        self.pdf_thread.finished.connect(lambda temp_path, temp_dir: self._on_pdf_finished(temp_path, temp_dir, save_path))
        self.pdf_thread.error.connect(self._on_pdf_error)
        self.pdf_thread.progress.connect(self.progress_dialog.setValue)
        self.progress_dialog.canceled.connect(self.pdf_thread.requestInterruption)
        
        self.pdf_thread.start()
        self.progress_dialog.exec_()
    
    def _on_pdf_finished(self, temp_path: str, temp_dir: str, save_path: str):
        self.progress_dialog.setValue(100)
        try:
            import shutil
            shutil.copy2(temp_path, save_path)
            QMessageBox.information(self, "完了", f"PDFを保存しました: {save_path}")
        except Exception as e:
            self._on_pdf_error(f"PDFの保存に失敗しました: {e}")
        finally:
            try:
                if temp_dir and os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
            except Exception as e:
                logger.error(f"一時ディレクトリの削除中にエラーが発生しました: {e}")

    def _on_pdf_error(self, message: str):
        self.progress_dialog.close(); QMessageBox.critical(self, "エラー", f"PDF生成に失敗しました:\n{message}")

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls(): event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        files = [url.toLocalFile() for url in event.mimeData().urls()]
        supported = ['.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp']
        image_files = [f for f in files if os.path.splitext(f)[1].lower() in supported]
        current_paths = self.image_manager_panel.get_image_paths()
        current_paths.extend(image_files)
        self.image_manager_panel.set_image_paths(current_paths)

    def closeEvent(self, event: Any):
        try:
            self.settings.save_to_file(SETTINGS_FILE)
        except Exception as e: QMessageBox.warning(self, "警告", f"終了時の設定保存に失敗しました: {e}")
        super().closeEvent(event)