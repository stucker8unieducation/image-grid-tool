# app/widgets/preview_panel.py
import logging
from typing import List

from PyQt5.QtCore import QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (QFrame, QLabel, QProgressDialog, QScrollArea, QVBoxLayout, QWidget)

from app.core.settings import GridSettings, MM_TO_PT
from app.threads.thumbnail_loader import ThumbnailLoader

logger = logging.getLogger(__name__)

class PreviewPanel(QWidget):
    """画像グリッドのプレビューを表示するパネル"""
    def __init__(self, settings: GridSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.image_paths: List[str] = []
        self.thumbnails: List[QPixmap] = []
        self.thumbnail_loader: ThumbnailLoader = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        self.info_label = QLabel("画像を左のパネルから追加してください。")
        self.info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.info_label)

        scroll_area = QScrollArea(); scroll_area.setWidgetResizable(True); scroll_area.setAlignment(Qt.AlignCenter)
        self.preview_frame = QFrame()
        self.preview_frame.paintEvent = self._paint_preview_event
        self.preview_frame.setStyleSheet("background-color: #f0f0f0;") # 背景色を少し灰色に
        scroll_area.setWidget(self.preview_frame)
        layout.addWidget(scroll_area)
    
    def on_settings_updated(self):
        """設定が変更された時に呼び出されるスロット"""
        self._update_info_label()
        self.preview_frame.update()

    def update_preview(self, image_paths: List[str]):
        self.image_paths = image_paths
        if not self.image_paths:
            self.thumbnails.clear(); self._update_info_label(); self.preview_frame.update()
            return
            
        if self.thumbnail_loader and self.thumbnail_loader.isRunning():
            self.thumbnail_loader.requestInterruption(); self.thumbnail_loader.wait()
        
        self.thumbnail_progress = QProgressDialog("サムネイルを準備中...", "キャンセル", 0, 100, self)
        self.thumbnail_progress.setWindowModality(Qt.WindowModal)
        
        self.thumbnail_loader = ThumbnailLoader(self.image_paths, self)
        self.thumbnail_loader.thumbnailsReady.connect(self._on_thumbnails_ready)
        self.thumbnail_loader.progress.connect(self.thumbnail_progress.setValue)
        self.thumbnail_progress.canceled.connect(self.thumbnail_loader.requestInterruption)
        self.thumbnail_loader.start()
        self.thumbnail_progress.exec_()

    def _on_thumbnails_ready(self, thumbnails: List[QPixmap]):
        self.thumbnail_progress.setValue(100)
        self.thumbnails = thumbnails; self._update_info_label(); self.preview_frame.update()

    def _update_info_label(self):
        if not self.image_paths:
            self.info_label.setText("画像を左のパネルから追加してください。")
            return
        rows, cols, num_pages = self.calculate_grid_dimensions()
        info = (f"画像数: {len(self.image_paths)} | "
                f"グリッド: {rows}行 × {cols}列 | "
                f"推定ページ数: {num_pages}")
        self.info_label.setText(info)
        
    def calculate_grid_dimensions(self):
        s = self.settings; page_w, page_h = s.page_size
        p_width = page_w - (s.margin_left_mm + s.margin_right_mm) * MM_TO_PT
        p_height = page_h - (s.margin_top_mm + s.margin_bottom_mm) * MM_TO_PT
        if p_width <=0 or p_height <= 0: return 0, 0, 0
        
        col_w_pt = s.col_width_mm * MM_TO_PT
        row_h_pt = s.row_height_mm * MM_TO_PT
        if col_w_pt <= 0 or row_h_pt <= 0: return 0, 0, 0

        cols = max(1, int(p_width / col_w_pt)); rows = max(1, int(p_height / row_h_pt))
        cells_per_page = cols * rows
        if cells_per_page == 0: return cols, rows, 0
        
        num_pages = (len(self.image_paths) + cells_per_page - 1) // cells_per_page
        return rows, cols, max(1, num_pages)

    def _paint_preview_event(self, event):
        painter = QPainter(self.preview_frame)
        painter.setRenderHint(QPainter.Antialiasing); painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        frame_w, frame_h = self.preview_frame.width(), self.preview_frame.height()
        page_w_pt, page_h_pt = self.settings.page_size
        
        aspect_ratio_frame = frame_w / frame_h
        aspect_ratio_page = page_w_pt / page_h_pt

        if aspect_ratio_frame > aspect_ratio_page:
            draw_h = frame_h - 20; draw_w = draw_h * aspect_ratio_page
        else:
            draw_w = frame_w - 20; draw_h = draw_w / aspect_ratio_page

        offset_x, offset_y = (frame_w - draw_w) / 2, (frame_h - draw_h) / 2
        
        painter.setBrush(Qt.white); painter.setPen(Qt.black)
        paper_rect = QRectF(offset_x, offset_y, draw_w, draw_h)
        painter.drawRect(paper_rect)

        if not self.image_paths or not self.thumbnails:
            painter.end()
            return

        s = self.settings
        rows, cols, _ = self.calculate_grid_dimensions()

        margin_l_px = draw_w * (s.margin_left_mm * MM_TO_PT) / page_w_pt
        margin_r_px = draw_w * (s.margin_right_mm * MM_TO_PT) / page_w_pt
        margin_t_px = draw_h * (s.margin_top_mm * MM_TO_PT) / page_h_pt
        margin_b_px = draw_h * (s.margin_bottom_mm * MM_TO_PT) / page_h_pt
        
        p_w = draw_w - (margin_l_px + margin_r_px); p_h = draw_h - (margin_t_px + margin_b_px)
        
        # 描画は左上原点なので、Y軸の計算に注意
        origin_x, origin_y = offset_x + margin_l_px, offset_y + margin_t_px
        
        cell_w, cell_h = p_w / cols, p_h / rows
        for i in range(min(len(self.thumbnails), rows * cols)):
            r, c = i // cols, i % cols
            thumb = self.thumbnails[i]
            
            cell_x, cell_y = origin_x + c * cell_w, origin_y + r * cell_h
            target_rect = QRectF(cell_x, cell_y, cell_w, cell_h)
            
            pixmap_scaled = thumb.scaled(target_rect.size().toSize(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            px, py = cell_x + (cell_w - pixmap_scaled.width()) / 2, cell_y + (cell_h - pixmap_scaled.height()) / 2
            painter.drawPixmap(int(px), int(py), pixmap_scaled)
            
        if s.grid_line_visible:
            pen = QPen(s.grid_color); pen.setWidth(s.grid_width); painter.setPen(pen)
            for c in range(cols + 1):
                x = origin_x + c * cell_w
                painter.drawLine(int(x), int(origin_y), int(x), int(origin_y + p_h))
            for r in range(rows + 1):
                y = origin_y + r * cell_h
                painter.drawLine(int(origin_x), int(y), int(origin_x + p_w), int(y))
        painter.end()
