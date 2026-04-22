# 主窗口业务逻辑类
# Robusr 2026.4.19

# -*- coding: utf-8 -*-

import sys
from PyQt5.QtWidgets import QApplication, QMainWindow
# from PyQt5.QtCore import pyqtSlot, pyqtSignal, Qt
# from PyQt5.QtWidgets import
# from PyQt5.QtGui import
# from PyQt5.QtSql import
# from PyQt5.QtMultimedia import
# from PyQt5.QtMultimediaWidgets import

import res_rc

from ui_MonitorAppMainWindow import Ui_MainWindow

class MonitorMainWindow(QMainWindow):
    """主窗口功能基类"""
    def __init__(self,parent=None):
        super().__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.setWindowTitle("Magnetic Foot Monitor")

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
            self.ui.pushButton_A_Begin.clicked.disconnect()
        except:
            pass

        try:
            self.ui.pushButton_A_Finish.clicked.disconnect()
        except:
            pass

        try:
            self.ui.pushButton_B_Begin.clicked.disconnect()
        except:
            pass

        try:
            self.ui.pushButton_B_Finish.clicked.disconnect()
        except:
            pass

        try:
            self.ui.pushButton_C_Begin.clicked.disconnect()
        except:
            pass

        try:
            self.ui.pushButton_C_Finish.clicked.disconnect()
        except:
            pass

        try:
            self.ui.pushButton_D_Begin.clicked.disconnect()
        except:
            pass

        try:
            self.ui.pushButton_D_Finish.clicked.disconnect()
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
        # self.ui.pushButton_A_Begin.clicked.connect(self.on_pushButton_A_Begin_clicked)
        # self.ui.pushButton_A_Finish.clicked.connect(self.on_pushButton_A_Finish_clicked)
        # self.ui.pushButton_B_Begin.clicked.connect(self.on_pushButton_B_Begin_clicked)
        # self.ui.pushButton_B_Finish.clicked.connect(self.on_pushButton_B_Finish_clicked)
        # self.ui.pushButton_C_Begin.clicked.connect(self.on_pushButton_C_Begin_clicked)
        # self.ui.pushButton_C_Finish.clicked.connect(self.on_pushButton_C_Finish_clicked)
        # self.ui.pushButton_D_Begin.clicked.connect(self.on_pushButton_D_Begin_clicked)
        # self.ui.pushButton_D_Finish.clicked.connect(self.on_pushButton_D_Finish_clicked)
        self.ui.pushButton_Begin.clicked.connect(self.on_pushButton_Begin_clicked)
        self.ui.pushButton_Finish.clicked.connect(self.on_pushButton_Finish_clicked)
        self.ui.pushButton_Send.clicked.connect(self.on_pushButton_Send_clicked)
        self.ui.pushButton_Refresh.clicked.connect(self.on_pushButton_Refresh_clicked)
        self.ui.pushButton_Reset.clicked.connect(self.on_pushButton_Reset_clicked)


    def on_pushButton_Connect_clicked(self):
        """信号连接"""
        print("Connect")
        pass

    def on_pushButton_Disconnect_clicked(self):
        """信号断开连接"""
        print("Disconnect")
        pass

    # def on_pushButton_A_Begin_clicked(self):
    #     """磁足A启动"""
    #     print("Foot A Begin")
    #     pass
    #
    # def on_pushButton_A_Finish_clicked(self):
    #     """磁足A关闭"""
    #     print("Foot A Finish")
    #     pass
    #
    # def on_pushButton_B_Begin_clicked(self):
    #     """磁足B启动"""
    #     print("Foot B Begin")
    #     pass
    #
    # def on_pushButton_B_Finish_clicked(self):
    #     """磁足B关闭"""
    #     print("Foot B Finish")
    #     pass
    #
    # def on_pushButton_C_Begin_clicked(self):
    #     """磁足C启动"""
    #     print("Foot C Begin")
    #     pass
    #
    # def on_pushButton_C_Finish_clicked(self):
    #     """磁足C关闭"""
    #     print("Foot C Finish")
    #     pass
    #
    # def on_pushButton_D_Begin_clicked(self):
    #     """磁足D启动"""
    #     print("Foot D Begin")
    #     pass
    #
    # def on_pushButton_D_Finish_clicked(self):
    #     """磁足D关闭"""
    #     print("Foot D Finish")
    #     pass

    def on_pushButton_Begin_clicked(self):
        """磁足整体启动"""
        print("Foot Global Begin")
        pass

    def on_pushButton_Finish_clicked(self):
        """磁足整体启动"""
        print("Foot Global Finish")
        pass

    def on_pushButton_Send_clicked(self):
        """磁足整体启动"""
        print("Send Message")
        pass

    def on_pushButton_Refresh_clicked(self):
        print("Refresh Message")
        pass

    def on_pushButton_Reset_clicked(self):
        print("Reset Message")
        pass


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MonitorMainWindow()
    window.show()
    sys.exit(app.exec_())