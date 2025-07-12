### プロジェクトのディレクトリ構造

以下は、このプロジェクトで採用するディレクトリ構造です。

```
image-grid-tool/
├── main.py                     # アプリケーションのエントリーポイント
├── app/
│   ├── __init__.py               # (空のファイル)
│   ├── main_window.py          # ImageGridApp (QMainWindow) クラス
│   ├── widgets/                # UIコンポーネント (QWidget)
│   │   ├── __init__.py           # (空のファイル)
│   │   ├── image_manager_panel.py # ImageManagerPanel クラス
│   │   ├── settings_panel.py      # SettingsPanel クラス
│   │   └── preview_panel.py       # PreviewPanel クラス
│   ├── core/                   # アプリケーションのコアロジック
│   │   ├── __init__.py           # (空のファイル)
│   │   ├── settings.py           # GridSettings データクラス
│   │   └── pdf_generator.py      # PDFGenerationThread クラス
│   └── threads/                # バックグラウンドスレッド
│       ├── __init__.py           # (空のファイル)
│       └── thumbnail_loader.py   # ThumbnailLoader クラス
├── settings.json               # (実行時に生成される設定ファイル)
└── PROJECT_STRUCTURE.md        # (このファイル)
```

**注意:** `__init__.py` は、そのディレクトリがPythonのパッケージであることを示すための空ファイルです。必ず作成してください。

---

### 1. `main.py`

このファイルがアプリケーションの起動点です。

```python
# main.py
import sys

from PyQt5.QtWidgets import QApplication

from app.main_window import ImageGridApp


def main():
    """アプリケーションのメインエントリーポイント"""
    app = QApplication(sys.argv)
    window = ImageGridApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
```

---

### 2. `app/core/settings.py`

データクラス `GridSettings` と関連定数を定義します。

```python
# app/core/settings.py
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Tuple

from PyQt5.QtGui import QColor
from reportlab.lib.pagesizes import A3, A4

logger = logging.getLogger(__name__)

# --- 定数定義 ---
MM_TO_PT: float = 2.83465
SETTINGS_FILE: str = "grid_settings.json"
PREVIEW_THUMBNAIL_SIZE: Tuple[int, int] = (200, 200)

@dataclass
class GridSettings:
    """グリッドとページ設定を保持するデータクラス"""
    row_height_mm: float = 10.0
    col_width_mm: float = 10.0
    grid_line_visible: bool = True
    grid_color: QColor = field(default_factory=lambda: QColor(0, 0, 0))
    grid_width: int = 1
    page_size: Tuple[float, float] = A4
    margin_top_mm: float = 10.0
    margin_bottom_mm: float = 10.0
    margin_left_mm: float = 10.0
    margin_right_mm: float = 10.0
    output_dpi: int = 300 # PDF出力時の解像度(DPI)

    def to_dict(self) -> Dict[str, Any]:
        """設定をJSONシリアライズ可能な辞書に変換"""
        settings_dict = asdict(self)
        settings_dict['grid_color'] = self.grid_color.name() # #RRGGBB形式
        settings_dict['page_size'] = 'A4' if self.page_size == A4 else 'A3'
        return settings_dict

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GridSettings':
        """辞書から設定を復元"""
        known_keys = cls.__annotations__.keys()
        filtered_data = {k: v for k, v in data.items() if k in known_keys}
        
        if 'grid_color' in filtered_data:
            filtered_data['grid_color'] = QColor(filtered_data['grid_color'])
        if 'page_size' in filtered_data:
            filtered_data['page_size'] = A4 if filtered_data['page_size'] == 'A4' else A3
        return cls(**filtered_data)

    def save_to_file(self, file_path: str) -> None:
        """設定を指定されたファイルに保存"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f, indent=4)
            logger.info(f"設定を保存しました: {file_path}")
        except Exception as e:
            logger.error(f"設定の保存中にエラーが発生しました: {e}")
            raise

    @classmethod
    def load_from_file(cls, file_path: str) -> 'GridSettings':
        """設定をファイルから読み込む。失敗した場合はデフォルト設定を返す"""
        if not os.path.exists(file_path):
            logger.info(f"設定ファイルが見つからないため、デフォルト設定を生成します: {file_path}")
            return cls()
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return cls.from_dict(data)
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            logger.error(f"設定ファイルの読み込みまたは解析に失敗しました: {e}。デフォルト設定を使用します。")
            return cls()
```

---

### 3. `app/core/pdf_generator.py`

PDF生成スレッド `PDFGenerationThread` を定義します。

```python
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
```

---

### 4. `app/threads/thumbnail_loader.py`

サムネイル生成スレッド `ThumbnailLoader` を定義します。

```python
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

```
*補足:* `thumbnail_loader.py` のエラーハンドリングで `Qt.lightGray` を使うために、`from PyQt5.QtCore import Qt` を追加するか、メインモジュールでインポートされたものを渡す必要がありますが、このまま独立したモジュールとしても機能します。

---

### 5. `app/widgets/image_manager_panel.py`

`ImageManagerPanel` UIコンポーネントを定義します。

```python
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
```

---

### 6. `app/widgets/settings_panel.py`

`SettingsPanel` UIコンポーネントを定義します。

```python
# app/widgets/settings_panel.py
from typing import Tuple

from PyQt5.QtWidgets import (QCheckBox, QColorDialog, QComboBox,
                             QDoubleSpinBox, QGridLayout, QGroupBox, QLabel,
                             QPushButton, QSpinBox, QVBoxLayout, QWidget)
from PyQt5.QtCore import pyqtSignal
from reportlab.lib.pagesizes import A3, A4

from app.core.settings import GridSettings


class SettingsPanel(QWidget):
    """各種設定を行うパネル"""
    settingsChanged = pyqtSignal()

    def __init__(self, settings: GridSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._init_ui()
        self.update_ui_from_settings()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        grid_group = QGroupBox("グリッド設定")
        grid_layout = QGridLayout()
        self.row_height_spin = self._create_spinbox("行の高さ:", (1.0, 500.0), self.on_settings_changed)
        self.col_width_spin = self._create_spinbox("列の幅:", (1.0, 500.0), self.on_settings_changed)
        self.grid_visible_check = QCheckBox("グリッド線を表示")
        self.grid_visible_check.stateChanged.connect(self.on_settings_changed)
        self.grid_width_spin = self._create_int_spinbox("線の太さ:", (1, 10), self.on_settings_changed)
        self.grid_color_btn = QPushButton("線の色を選択")
        self.grid_color_btn.clicked.connect(self.select_grid_color)
        grid_layout.addWidget(self.row_height_spin[0], 0, 0)
        grid_layout.addWidget(self.row_height_spin[1], 0, 1)
        grid_layout.addWidget(self.col_width_spin[0], 1, 0)
        grid_layout.addWidget(self.col_width_spin[1], 1, 1)
        grid_layout.addWidget(self.grid_visible_check, 2, 0, 1, 2)
        grid_layout.addWidget(self.grid_width_spin[0], 3, 0)
        grid_layout.addWidget(self.grid_width_spin[1], 3, 1)
        grid_layout.addWidget(self.grid_color_btn, 4, 0, 1, 2)
        grid_group.setLayout(grid_layout)
        layout.addWidget(grid_group)

        page_group = QGroupBox("ページ設定")
        page_layout = QGridLayout()
        self.page_size_combo = QComboBox()
        self.page_size_combo.addItems(["A4", "A3"])
        self.page_size_combo.currentTextChanged.connect(self.on_settings_changed)
        self.margin_top = self._create_spinbox("上マージン:", (0.0, 100.0), self.on_settings_changed)
        self.margin_bottom = self._create_spinbox("下マージン:", (0.0, 100.0), self.on_settings_changed)
        self.margin_left = self._create_spinbox("左マージン:", (0.0, 100.0), self.on_settings_changed)
        self.margin_right = self._create_spinbox("右マージン:", (0.0, 100.0), self.on_settings_changed)
        page_layout.addWidget(QLabel("用紙サイズ:"), 0, 0); page_layout.addWidget(self.page_size_combo, 0, 1)
        page_layout.addWidget(self.margin_top[0], 1, 0); page_layout.addWidget(self.margin_top[1], 1, 1)
        page_layout.addWidget(self.margin_bottom[0], 2, 0); page_layout.addWidget(self.margin_bottom[1], 2, 1)
        page_layout.addWidget(self.margin_left[0], 3, 0); page_layout.addWidget(self.margin_left[1], 3, 1)
        page_layout.addWidget(self.margin_right[0], 4, 0); page_layout.addWidget(self.margin_right[1], 4, 1)
        page_group.setLayout(page_layout)
        layout.addWidget(page_group)
        
        output_group = QGroupBox("出力設定")
        output_layout = QGridLayout()
        self.dpi_spin = self._create_int_spinbox("解像度 (DPI):", (72, 1200), self.on_settings_changed)
        output_layout.addWidget(self.dpi_spin[0], 0, 0)
        output_layout.addWidget(self.dpi_spin[1], 0, 1)
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)
        
        layout.addStretch(1)

    def _create_spinbox(self, label, range_val, callback) -> Tuple[QLabel, QDoubleSpinBox]:
        lbl = QLabel(label); spin = QDoubleSpinBox(); spin.setRange(*range_val); spin.setSuffix(" mm"); spin.valueChanged.connect(callback)
        return lbl, spin

    def _create_int_spinbox(self, label, range_val, callback) -> Tuple[QLabel, QSpinBox]:
        lbl = QLabel(label); spin = QSpinBox(); spin.setRange(*range_val); spin.valueChanged.connect(callback)
        return lbl, spin
    
    def select_grid_color(self):
        color = QColorDialog.getColor(self.settings.grid_color, self, "グリッド線の色を選択")
        if color.isValid():
            self.settings.grid_color = color
            self.on_settings_changed()

    def update_settings_from_ui(self):
        s = self.settings
        s.row_height_mm = self.row_height_spin[1].value(); s.col_width_mm = self.col_width_spin[1].value()
        s.grid_line_visible = self.grid_visible_check.isChecked(); s.grid_width = self.grid_width_spin[1].value()
        s.page_size = A4 if self.page_size_combo.currentText() == "A4" else A3
        s.margin_top_mm = self.margin_top[1].value(); s.margin_bottom_mm = self.margin_bottom[1].value()
        s.margin_left_mm = self.margin_left[1].value(); s.margin_right_mm = self.margin_right[1].value()
        s.output_dpi = self.dpi_spin[1].value()
    
    def update_ui_from_settings(self):
        s = self.settings
        widgets_to_block = self.findChildren((QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox))
        for widget in widgets_to_block: widget.blockSignals(True)
        
        self.row_height_spin[1].setValue(s.row_height_mm); self.col_width_spin[1].setValue(s.col_width_mm)
        self.grid_visible_check.setChecked(s.grid_line_visible); self.grid_width_spin[1].setValue(s.grid_width)
        self.page_size_combo.setCurrentText("A4" if s.page_size == A4 else "A3")
        self.margin_top[1].setValue(s.margin_top_mm); self.margin_bottom[1].setValue(s.margin_bottom_mm)
        self.margin_left[1].setValue(s.margin_left_mm); self.margin_right[1].setValue(s.margin_right_mm)
        self.dpi_spin[1].setValue(s.output_dpi)
        
        for widget in widgets_to_block: widget.blockSignals(False)
        self.settingsChanged.emit() # 反映後にシグナルを送る

    def on_settings_changed(self):
        self.update_settings_from_ui()
        self.settingsChanged.emit()
```

---

### 7. `app/widgets/preview_panel.py`

`PreviewPanel` UIコンポーネントを定義します。

```python
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

```

---

### 8. `app/main_window.py`

そして、これら全てをまとめる `ImageGridApp` メインウィンドウです。

```python
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
        path, _ = QFileDialog.getSaveFileName(self, "設定ファイルを保存", "output.pdf", "JSON Files (*.json)")
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
        
        self.pdf_thread = PDFGenerationThread(self.image_paths, self.settings, self)
        self.pdf_thread.finished.connect(lambda data: self._on_pdf_finished(data, save_path))
        self.pdf_thread.error.connect(self._on_pdf_error)
        self.pdf_thread.progress.connect(self.progress_dialog.setValue)
        self.progress_dialog.canceled.connect(self.pdf_thread.requestInterruption)
        
        self.pdf_thread.start()
        self.progress_dialog.exec_()
    
    def _on_pdf_finished(self, pdf_data: bytes, save_path: str):
        self.progress_dialog.setValue(100)
        try:
            with open(save_path, 'wb') as f: f.write(pdf_data)
            QMessageBox.information(self, "完了", f"PDFを保存しました: {save_path}")
        except Exception as e: self._on_pdf_error(f"PDFの保存に失敗しました: {e}")

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

