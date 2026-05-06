# 主窗口业务逻辑类
# Robusr 2026.4.19

# -*- coding: utf-8 -*-

import sys
import time

from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox

import serial
import serial.tools.list_ports

import re

from PyQt5.QtCore import pyqtSlot, pyqtSignal, Qt, QTimer
# from PyQt5.QtWidgets import
# from PyQt5.QtGui import
# from PyQt5.QtSql import
# from PyQt5.QtMultimedia import
# from PyQt5.QtMultimediaWidgets import

import res_rc

import matplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import math

import ctypes

from ui_MonitorAppMainWindow import Ui_MainWindow

ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("myappid")
matplotlib.use("Qt5Agg")


class MonitorMainWindow(QMainWindow):
    """主窗口功能基类"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.setWindowTitle("Magnetic Foot Monitor")

        self.ser = serial.Serial()
        self.port_check()
        # self.ddd = opengl_widget()

        self.tit = 0
        self.timer = QTimer(self)
        # self.timer.timeout.connect(self.DATA)

        self.timer1 = QTimer()

        self.ui.pushButton_Connect.clicked.connect(self.port_open)
        self.ui.pushButton_Disconnect.clicked.connect(self.port_close)
        self.ui.comboBox_DataPort.currentTextChanged.connect(self.port_imf)

        self.timer1 = QTimer()

        # 断开QtCore.QMetaObject.connectSlotsByName(MainWindow)自动连接
        try:
            self.ui.pushButton_Connect.clicked.disconnect()
        except:
            pass

        try:
            self.ui.pushButton_Disconnect.clicked.disconnect()
        except:
            pass

        try:
            self.ui.pushButton_Begin.clicked.disconnect()
        except:
            pass

        try:
            self.ui.pushButton_Finish.clicked.disconnect()
        except:
            pass

        try:
            self.ui.pushButton_Send.clicked.disconnect()
        except:
            pass

        try:
            self.ui.pushButton_Refresh.clicked.disconnect()
        except:
            pass

        try:
            self.ui.pushButton_Reset.clicked.disconnect()
        except:
            pass

        # 单次连接重构
        self.ui.pushButton_Connect.clicked.connect(self.on_pushButton_Connect_clicked)
        self.ui.pushButton_Disconnect.clicked.connect(self.on_pushButton_Disconnect_clicked)

        self.ui.pushButton_Begin.clicked.connect(self.on_pushButton_Begin_clicked)
        self.ui.pushButton_Finish.clicked.connect(self.on_pushButton_Finish_clicked)

        self.ui.pushButton_Send.clicked.connect(self.on_pushButton_Send_clicked)
        self.ui.pushButton_Refresh.clicked.connect(self.on_pushButton_Refresh_clicked)
        self.ui.pushButton_Reset.clicked.connect(self.on_pushButton_Reset_clicked)

    def on_pushButton_Connect_clicked(self):
        """信号连接"""
        print("Connect")
        # self.ui.plainTextEdit_Log.setPlainText("Connect")
        self.ui.plainTextEdit_Log.appendPlainText("Connect")
        pass

    def on_pushButton_Disconnect_clicked(self):
        """信号断开连接"""
        print("Disconnect")
        # self.ui.plainTextEdit_Log.setPlainText("Disconnect")
        self.ui.plainTextEdit_Log.appendPlainText("Disconnect")
        pass

    def on_pushButton_Begin_clicked(self):
        """磁足整体启动"""
        print("Begin")
        # self.ui.plainTextEdit_Log.setPlainText("Begin")
        self.ui.plainTextEdit_Log.appendPlainText("Begin")
        pass

    def on_pushButton_Finish_clicked(self):
        """磁足整体启动"""
        print("Finish")
        # self.ui.plainTextEdit_Log.setPlainText("Finish")
        self.ui.plainTextEdit_Log.appendPlainText("Finish")
        pass

    def on_pushButton_Send_clicked(self):
        """磁足整体启动"""
        print("Send Message")
        # self.ui.plainTextEdit_Log.setPlainText("Send Message")
        self.ui.plainTextEdit_Log.appendPlainText("Send Message")
        pass

    def on_pushButton_Refresh_clicked(self):
        print("Refresh Message")
        # self.ui.plainTextEdit_Log.setPlainText("Refresh Message")
        self.ui.plainTextEdit_Log.appendPlainText("Refresh Message")
        pass

    def on_pushButton_Reset_clicked(self):
        print("Reset Message")
        # self.ui.plainTextEdit_Log.setPlainText("Reset Message")
        self.ui.plainTextEdit_Log.appendPlainText("Reset Message")
        pass

    def port_check(self):
        # 检测所有存在的串口，将信息存储在字典中
        self.Com_Dict = {}  # 创建一个字典，字典是可变的容器
        port_list = list(serial.tools.list_ports.comports())  # list是序列，一串数据，可以追加数据
        self.ui.comboBox_DataPort.clear()  # s1__box_2为串口选择列表
        for port in port_list:
            self.Com_Dict["%s" % port[0]] = "%s" % port[1]
            self.ui.comboBox_DataPort.addItem(port[0])  # 将检测到的串口放置到s1__box_2串口选择列表
        if len(self.Com_Dict) == 0:
            pass

    # ------------------串口选择下拉框选择com口
    def port_imf(self):
        # 显示选定的串口的详细信息
        imf_s = self.ui.comboBox_DataPort.currentText()  # 当前显示的com口
        if imf_s != "":
            self.ui.plainTextEdit_Log.setPlainText(self.Com_Dict[self.ui.comboBox_DataPort.currentText()])

    # -------------------打开串口
    def port_open(self):
        self.ser.port = self.ui.comboBox_DataPort.currentText()
        print(self.ui.comboBox_DataPort.currentText())  # 串口选择框
        self.ser.baudrate = int(9600)  # 波特率输入框
        self.ser.bytesize = int(8)  # 数据位输入框
        self.ser.stopbits = int(1)  # 停止位输入框
        self.ser.parity = "N"  # 校验位输入框
        try:
            self.ser.open()
        except:
            QMessageBox.critical(self, "Port Error", "此串口不能被打开！")
        self.timer.start(5)
        if self.ser.isOpen():  # 打开串口按下，禁用打开按钮，启用关闭按钮
            self.ui.pushButton_Connect.setEnabled(False)  # 禁用打开按钮
            self.ui.plainTextEdit_Log.setPlainText("串口状态（已开启）")

    def port_close(self):
        self.timer.stop()  # 停止计时器
        self.timer1.stop()  # 停止图形显示计时器
        try:
            self.ser.close()
        except:
            pass
        self.ui.pushButton_Connect.setEnabled(True)
        self.ui.plainTextEdit_Log.setPlainText("串口已关闭")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MonitorMainWindow()
    window.show()
    sys.exit(app.exec_())
