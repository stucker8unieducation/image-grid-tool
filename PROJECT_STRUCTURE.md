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