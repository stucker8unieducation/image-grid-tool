# app/core/pdf_generator.py
import io
import logging
import os
import tempfile
import shutil
from typing import List

from PIL import Image, UnidentifiedImageError
from PyQt5.QtCore import QThread, pyqtSignal
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .settings import GridSettings, MM_TO_PT

logger = logging.getLogger(__name__)

class PDFGenerationThread(QThread):
    """PDF生成をバックグラウンドで実行するスレッド"""
    finished = pyqtSignal(str, str)  # 成功時に一時ファイルパスとディレクトリを送信
    error = pyqtSignal(str)     # エラー時にメッセージを送信
    progress = pyqtSignal(int)  # 進捗状況を送信

    def __init__(self, image_paths: List[str], settings: GridSettings):
        super().__init__()
        self.image_paths = image_paths
        self.settings = settings
        self.temp_dir = None

    def run(self) -> None:
        try:
            self.temp_dir = tempfile.mkdtemp()  # 一時ディレクトリを作成
            file_path = os.path.join(self.temp_dir, "output.pdf")
            pdf = canvas.Canvas(file_path, pagesize=self.settings.page_size)
            
            # 印刷可能域を計算
            page_width, page_height = self.settings.page_size
            printable_width = page_width - (self.settings.margin_left_mm + self.settings.margin_right_mm) * MM_TO_PT
            printable_height = page_height - (self.settings.margin_top_mm + self.settings.margin_bottom_mm) * MM_TO_PT
            
            total_images = len(self.image_paths)
            
            # 行と列の数を計算（印刷可能域内で）
            col_width_pt = self.settings.col_width_mm * MM_TO_PT
            row_height_pt = self.settings.row_height_mm * MM_TO_PT
            cols = max(1, int(printable_width / col_width_pt))
            rows = max(1, int(printable_height / row_height_pt))
            
            # 実際のセルサイズを計算（印刷可能域を均等に分割）
            actual_col_width_pt = printable_width / cols
            actual_row_height_pt = printable_height / rows
            
            cells_per_page = cols * rows # 1ページあたりのセル数
            
            # 総ページ数を計算（全てのセルを埋めるため）
            # 画像が1枚も指定されていない場合は、少なくとも1ページは生成する
            total_pages = max(1, (total_images + cells_per_page - 1) // cells_per_page) if total_images > 0 else 1

            img_idx = 0
            for page_num in range(total_pages):
                logger.info(f"{page_num + 1}ページ目の生成を開始します。")

                if self.settings.grid_line_visible:
                    self._draw_grid_lines(pdf, cols, rows, actual_col_width_pt, actual_row_height_pt,
                                        printable_width, printable_height,
                                        self.settings.margin_left_mm * MM_TO_PT,
                                        self.settings.margin_bottom_mm * MM_TO_PT)
                
                for r in range(rows):
                    if self.isInterruptionRequested(): return
                    for c in range(cols):
                        # 現在のページ内のセルインデックス
                        current_cell_in_page = r * cols + c
                        
                        # 画像リストのインデックスを循環させる
                        image_to_use_idx = current_cell_in_page % len(self.image_paths) if self.image_paths else 0

                        progress_val = int(((page_num * cells_per_page) + current_cell_in_page + 1) / (total_pages * cells_per_page) * 100)
                        self.progress.emit(progress_val)
                        
                        if self.image_paths: # 画像が指定されている場合のみ処理
                            try:
                                self._process_image(pdf, self.image_paths[image_to_use_idx], 
                                                  r, c, actual_col_width_pt, actual_row_height_pt,
                                                  page_height, self.temp_dir,
                                                  self.settings.margin_left_mm * MM_TO_PT,
                                                  self.settings.margin_bottom_mm * MM_TO_PT)
                            except UnidentifiedImageError as e:
                                logger.error(f"画像の読み込みに失敗しました: {self.image_paths[image_to_use_idx]}, エラー: {e}")
                                pass # エラーがあっても処理を続行
                            except Exception as e:
                                logger.error(f"画像の処理中にエラーが発生しました: {self.image_paths[image_to_use_idx]}, エラー: {e}")
                                pass # エラーがあっても処理を続行
                
                if page_num < total_pages - 1: # 最後のページでなければ新しいページを追加
                    pdf.showPage()
            
            # グリッド線の描画（マージンを考慮）
            if self.settings.grid_line_visible:
                self._draw_grid_lines(pdf, cols, rows, actual_col_width_pt, actual_row_height_pt,
                                    printable_width, printable_height,
                                    self.settings.margin_left_mm * MM_TO_PT,
                                    self.settings.margin_bottom_mm * MM_TO_PT)
            
            pdf.save()
            self.finished.emit(file_path, self.temp_dir)
            
        except Exception as e:
            logger.error(f"PDF生成中にエラーが発生しました: {e}")
            self.error.emit(str(e))

    def __del__(self):
        """デストラクタ：一時ディレクトリの削除"""
        try:
            if hasattr(self, 'temp_dir') and self.temp_dir and os.path.exists(self.temp_dir):
                import shutil
                shutil.rmtree(self.temp_dir)
        except Exception as e:
            logger.error(f"一時ディレクトリの削除中にエラーが発生しました: {e}")

    def _process_image(self, pdf: canvas.Canvas, img_path: str, row: int, col: int,
                      col_width_pt: float, row_height_pt: float, page_height: float,
                      temp_dir: str, margin_left_pt: float, margin_bottom_pt: float) -> None:
        """画像を処理してPDFに配置"""
        with Image.open(img_path) as img:
            # メタデータを含めて完全なコピーを作成
            img = img.copy()

            # 画像の色空間を確認
            original_mode = img.mode

            # 高品質なリサイズ
            img_width, img_height = img.size
            img_aspect = img_width / img_height
            cell_aspect = col_width_pt / row_height_pt
            
            if img_aspect > cell_aspect:
                new_width = col_width_pt
                new_height = col_width_pt / img_aspect
            else:
                new_height = row_height_pt
                new_width = row_height_pt * img_aspect
            
            # Lanczosフィルターによる高品質なリサイズ
            # 解像度を維持するために、より大きなサイズでリサイズ
            scale_factor = 3.0  # 解像度を2倍に
            img = img.resize(
                (int(new_width * scale_factor), int(new_height * scale_factor)), 
                Image.Resampling.LANCZOS
            )

            # 色空間変換の詳細処理
            if original_mode == 'RGBA':
                # アルファチャンネルを白背景に
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])
                img = background

            # RGBからCMYKへの変換を試みる
            try:
                if img.mode != 'CMYK':
                    # PIL標準のCMYK変換
                    img_cmyk = img.convert('CMYK')
                else:
                    img_cmyk = img
            except Exception as e:
                print(f"CMYK変換エラー: {e}")
                # エラーが発生した場合はRGBのまま処理を続行
                img_cmyk = img.convert('RGB')

            # 高品質な一時ファイル保存（TIFFを推奨）
            temp_img_path = os.path.join(temp_dir, f"temp_{row}_{col}.tiff")
            img_cmyk.save(
                temp_img_path, 
                format='TIFF', 
                compression='tiff_deflate',
                dpi=(600, 600)  # 高解像度設定
            )
            
            # セル内でのセンタリング計算（マージンを考慮）
            x_offset = margin_left_pt + col * col_width_pt + (col_width_pt - new_width) / 2
            # PDFの座標系に合わせてY座標を計算（原点が左下）
            y_offset = margin_bottom_pt + row * row_height_pt + (row_height_pt - new_height) / 2
            
            # PDFに画像を配置
            pdf.drawImage(
                temp_img_path, 
                x_offset, 
                y_offset, 
                new_width, 
                new_height,
                preserveAspectRatio=True,
                mask='auto'
            )

    def _draw_grid_lines(self, pdf: canvas.Canvas, cols: int, rows: int,
                        col_width_pt: float, row_height_pt: float,
                        printable_width: float, printable_height: float,
                        margin_left_pt: float, margin_bottom_pt: float) -> None:
        """グリッド線を描画する"""
        r, g, b = (self.settings.grid_color.red() / 255.0,
                  self.settings.grid_color.green() / 255.0,
                  self.settings.grid_color.blue() / 255.0)
        pdf.setStrokeColorRGB(r, g, b)
        pdf.setLineWidth(self.settings.grid_width)
        
        # 垂直線（マージンを考慮）
        for col in range(cols + 1):
            x = margin_left_pt + col * col_width_pt
            pdf.line(x, margin_bottom_pt, x, margin_bottom_pt + printable_height)
        
        # 水平線（マージンを考慮）
        for row in range(rows + 1):
            y = margin_bottom_pt + row * row_height_pt
            pdf.line(margin_left_pt, y, margin_left_pt + printable_width, y)