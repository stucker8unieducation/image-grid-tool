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
