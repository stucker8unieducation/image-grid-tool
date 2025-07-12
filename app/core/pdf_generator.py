# app/core/pdf_generator.py
import io
import logging
from typing import List

from PIL import Image, UnidentifiedImageError
from PyQt5.QtCore import QThread, pyqtSignal
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .settings import GridSettings, MM_TO_PT

logger = logging.getLogger(__name__)

class PDFGenerationThread(QThread):
    """PDF生成をバックグラウンドで実行するスレッド"""
    finished = pyqtSignal(bytes)
    error = pyqtSignal(str)
    progress = pyqtSignal(int)

    def __init__(self, image_paths: List[str], settings: GridSettings, parent=None):
        super().__init__(parent)
        self.image_paths = image_paths
        self.settings = settings

    def run(self) -> None:
        try:
            pdf_buffer = io.BytesIO()
            pdf = canvas.Canvas(pdf_buffer, pagesize=self.settings.page_size)

            page_width, page_height = self.settings.page_size
            margin_left_pt = self.settings.margin_left_mm * MM_TO_PT
            margin_right_pt = self.settings.margin_right_mm * MM_TO_PT
            margin_top_pt = self.settings.margin_top_mm * MM_TO_PT
            margin_bottom_pt = self.settings.margin_bottom_mm * MM_TO_PT

            printable_width = page_width - (margin_left_pt + margin_right_pt)
            printable_height = page_height - (margin_top_pt + margin_bottom_pt)

            col_width_pt = self.settings.col_width_mm * MM_TO_PT
            row_height_pt = self.settings.row_height_mm * MM_TO_PT
            
            if col_width_pt <= 0 or row_height_pt <= 0:
                self.error.emit("セルの幅と高さは0より大きい必要があります。")
                return

            cols_per_page = max(1, int(printable_width / col_width_pt))
            rows_per_page = max(1, int(printable_height / row_height_pt))
            cells_per_page = cols_per_page * rows_per_page

            if cells_per_page == 0:
                self.error.emit("用紙サイズやマージンの設定で、1つもセルを配置できません。")
                return

            total_images = len(self.image_paths)
            img_idx = 0
            page_count = 0

            while img_idx < total_images:
                page_count += 1
                logger.info(f"{page_count}ページ目の生成を開始します。")

                if self.settings.grid_line_visible:
                    self._draw_grid_lines(pdf, cols_per_page, rows_per_page, printable_width, printable_height, margin_left_pt, margin_bottom_pt)
                
                for r in range(rows_per_page):
                    if self.isInterruptionRequested(): return
                    for c in range(cols_per_page):
                        if img_idx >= total_images: break
                        
                        progress_val = int((img_idx + 1) / total_images * 100)
                        self.progress.emit(progress_val)
                        
                        try:
                            self._place_image_on_canvas(pdf, self.image_paths[img_idx], r, c, col_width_pt, row_height_pt, page_height, margin_left_pt, margin_bottom_pt)
                        except Exception as e:
                            logger.error(f"画像処理エラー: {self.image_paths[img_idx]}, {e}")
                        
                        img_idx += 1
                    if img_idx >= total_images: break

                if img_idx < total_images:
                    pdf.showPage()

            pdf.save()
            pdf_buffer.seek(0)
            self.finished.emit(pdf_buffer.getvalue())

        except Exception as e:
            logger.error(f"PDF生成中に予期せぬエラーが発生しました: {e}", exc_info=True)
            self.error.emit(f"予期せぬエラー: {e}")

    def _place_image_on_canvas(self, pdf, img_path, row, col, w_pt, h_pt, page_h, m_left, m_bottom):
        with Image.open(img_path) as img:
            target_w_px = w_pt / 72.0 * self.settings.output_dpi
            target_h_px = h_pt / 72.0 * self.settings.output_dpi
            
            img.thumbnail((target_w_px, target_h_px), Image.Resampling.LANCZOS)
            
            if img.mode == 'RGBA':
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])
                img = background
            elif img.mode in ('P', 'LA'):
                img = img.convert('RGB')
            elif img.mode != 'CMYK':
                img = img.convert('RGB')

            img_buffer = io.BytesIO()
            img.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            image_reader = ImageReader(img_buffer)
            
            img_w, img_h = image_reader.getSize()
            img_aspect = img_w / img_h if img_h else 1
            cell_aspect = w_pt / h_pt if h_pt else 1
            
            if img_aspect > cell_aspect:
                draw_w, draw_h = w_pt, w_pt / img_aspect
            else:
                draw_w, draw_h = h_pt * img_aspect, h_pt

            x = m_left + col * w_pt + (w_pt - draw_w) / 2
            y = m_bottom + row * h_pt + (h_h - draw_h) / 2
            pdf.drawImage(image_reader, x, y, width=draw_w, height=draw_h, mask='auto')
    
    def _draw_grid_lines(self, pdf, cols, rows, p_width, p_height, m_left, m_bottom):
        color = self.settings.grid_color
        pdf.setStrokeColorRGB(color.redF(), color.greenF(), color.blueF())
        pdf.setLineWidth(self.settings.grid_width)
        
        col_w = p_width / cols if cols else 0
        row_h = p_height / rows if rows else 0

        for i in range(cols + 1):
            x = m_left + i * col_w
            pdf.line(x, m_bottom, x, m_bottom + p_height)
        for i in range(rows + 1):
            y = m_bottom + i * row_h
            pdf.line(m_left, y, m_left + p_width, y)