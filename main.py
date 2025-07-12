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
