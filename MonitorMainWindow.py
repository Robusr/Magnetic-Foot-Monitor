# Robusr 2026.4.19
# 主窗口业务逻辑类

# -*- coding: utf-8 -*-

import sys
from PyQt5.QtWidgets import QApplication, QMainWindow
# from PyQt5.QtCore import pyqtSlot, pyqtSignal, Qt
# from PyQt5.QtWidgets import
# from PyQt5.QtGui import
# from PyQt5.QtSql import
# from PyQt5.QtMultimedia import
# from PyQt5.QtMultimediaWidgets import

from ui_MonitorAppMainWindow import Ui_MainWindow

class MonitorMainWindow(QMainWindow):
    """主窗口功能基类"""
    def __init__(self,parent=None):
        super().__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

    def on_pushButtonBegin_clicked(self):
        print("Begin")
        pass

    def on_pushButtonFinish_clicked(self):
        print("Finish")
        pass


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MonitorMainWindow()
    window.show()
    sys.exit(app.exec_())