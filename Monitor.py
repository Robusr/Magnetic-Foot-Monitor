# -*- coding: utf-8 -*-
"""
@File    : Monitor.py
@Author  : Robusr
@Date    : 2026/5/6 15:33
@Description: oyinstaller封装入口文件
@Software: PyCharm
"""

import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon
from MonitorMainWindow import MonitorMainWindow

app = QApplication(sys.argv)
icon = QIcon("MonitorQtApp/images/hammer.ico")
app.setWindowIcon(icon)
mainform = MonitorMainWindow()

mainform.show()
sys.exit(app.exec_())
