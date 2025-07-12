# app/threads/thumbnail_loader.py
import io
import logging
from typing import List

from PIL import Image, UnidentifiedImageError
from PyQt5.QtCore import QThread, pyqtSignal, QSize, Qt
from PyQt5.QtGui import QPixmap

from app.core.settings import PREVIEW_THUMBNAIL_SIZE

logger = logging.getLogger(__name__)

class ThumbnailLoader(QThread):
    """サムネイル生成をバックグラウンドで行うスレッド"""
    thumbnailsReady = pyqtSignal(list)
    progress = pyqtSignal(int)

    def __init__(self, image_paths: List[str], parent=None):
        super().__init__(parent)
        self.image_paths = image_paths

    def run(self):
        thumbnails = []
        total = len(self.image_paths)
        if total == 0:
            self.thumbnailsReady.emit([])
            return

        for i, path in enumerate(self.image_paths):
            if self.isInterruptionRequested():
                return
            try:
                with Image.open(path) as img:
                    if img.mode == 'CMYK': img = img.convert('RGB')
                    img.thumbnail(PREVIEW_THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
                    
                    buffer = io.BytesIO()
                    img.save(buffer, format='PNG')
                    buffer.seek(0)
                    
                    pixmap = QPixmap()
                    pixmap.loadFromData(buffer.getvalue())
                    thumbnails.append(pixmap)
            except (UnidentifiedImageError, FileNotFoundError, OSError) as e:
                logger.warning(f"サムネイル生成失敗: {path}, {e}")
                placeholder = QPixmap(QSize(*PREVIEW_THUMBNAIL_SIZE))
                placeholder.fill(Qt.lightGray) # Qtモジュールをインポートする必要あり
                thumbnails.append(placeholder)
            
            self.progress.emit(int((i + 1) / total * 100))
        
        self.thumbnailsReady.emit(thumbnails)
