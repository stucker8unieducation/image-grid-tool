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
