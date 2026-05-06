# -*- coding: utf-8 -*-
"""
@File    : MonitorMainWindow.py
@Author  : Robusr
@Date    : 2026/4/19 00:28
@Description: 主窗口业务逻辑类
@Software: PyCharm
"""

# 2026.5.6 优化：保留原始断开重连机制，新增Debug Hex发送、Begin控制、串口解析、图表更新

import sys
import time
import datetime
import re
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox
from PyQt5.QtCore import pyqtSlot, pyqtSignal, Qt, QTimer
import serial
import serial.tools.list_ports
import res_rc
import matplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
import matplotlib.pyplot as plt
import numpy as np
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

        # === 全局变量初始化 ===
        self.ser = serial.Serial()
        self.serial_buffer = b""
        self.module_states = {}
        self.plot_time = []
        self.plot_current = []
        self.plot_state = []
        self.max_plot_points = 100
        self.start_time = 0

        self.tit = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.receive_data)  # 连接数据接收
        self.timer1 = QTimer()

        # === 原始代码：第一次连接（用于触发后面的断开） ===
        self.ui.pushButton_Connect.clicked.connect(self.port_open)
        self.ui.pushButton_Disconnect.clicked.connect(self.port_close)
        self.ui.comboBox_DataPort.currentTextChanged.connect(self.port_imf)

        # === 图表初始化 ===
        self.figure_state = plt.figure()
        self.canvas_state = FigureCanvasQTAgg(self.figure_state)
        self.ui.gridLayout_State.addWidget(self.canvas_state, 0, 2, 2, 1)
        self.ax_state = self.canvas_state.figure.subplots(1, 1)
        self.ax_state.set_xlabel("Time (s)")
        self.ax_state.set_ylabel("State (1=Charge, 2=Discharge)")
        self.ax_state.set_ylim(0, 3)
        self.ax_state.set_xlim(0, 10)
        self.line_state, = self.ax_state.plot([], [], 'b-', label="Actual State")
        self.ax_state.legend()

        self.figure_current = plt.figure()
        self.canvas_current = FigureCanvasQTAgg(self.figure_current)
        self.ui.gridLayout_Current.addWidget(self.canvas_current, 0, 2, 2, 1)
        self.ax_current = self.canvas_current.figure.subplots(1, 1)
        self.ax_current.set_xlabel("Time (s)")
        self.ax_current.set_ylabel("Current (A)")
        self.ax_current.set_ylim(0, 25)
        self.ax_current.set_xlim(0, 10)
        self.line_current, = self.ax_current.plot([], [], 'r-', label="Actual Current")
        self.ax_current.legend()

        # === 原始代码：断开QtCore.QMetaObject.connectSlotsByName(MainWindow)自动连接 ===
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

        # === 原始代码：单次连接重构 ===
        self.ui.pushButton_Connect.clicked.connect(self.on_pushButton_Connect_clicked)
        self.ui.pushButton_Disconnect.clicked.connect(self.on_pushButton_Disconnect_clicked)
        self.ui.pushButton_Begin.clicked.connect(self.on_pushButton_Begin_clicked)
        self.ui.pushButton_Finish.clicked.connect(self.on_pushButton_Finish_clicked)
        self.ui.pushButton_Send.clicked.connect(self.on_pushButton_Send_clicked)
        self.ui.pushButton_Refresh.clicked.connect(self.on_pushButton_Refresh_clicked)
        self.ui.pushButton_Reset.clicked.connect(self.on_pushButton_Reset_clicked)

        # === 初始化UI ===
        self.port_check()
        self.init_ui_controls()
        self.log_message("系统初始化完成")
        self.log_message("提示：在Debug区域输入Hex字符串，点击下方Send发送原始包")

    def init_ui_controls(self):
        """初始化下拉框"""
        self.ui.comboBox_ID.clear()
        for i in range(1, 9):
            self.ui.comboBox_ID.addItem(f"{i:02X}", i)
        self.ui.comboBox_FN.clear()
        self.ui.comboBox_FN.addItem("左腿", 1)
        self.ui.comboBox_FN.addItem("右腿", 2)
        self.ui.comboBox_MODE.clear()
        self.ui.comboBox_MODE.addItem("充磁", 1)
        self.ui.comboBox_MODE.addItem("退磁", 2)
        self.ui.comboBox_BaudRate.setCurrentText("9600")

    def log_message(self, message):
        """带时间戳的日志"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.ui.plainTextEdit_Log.appendPlainText(f"[{timestamp}] {message}")
        self.ui.plainTextEdit_Log.verticalScrollBar().setValue(
            self.ui.plainTextEdit_Log.verticalScrollBar().maximum()
        )

    def debug_message(self, direction, data):
        """Debug区域显示原始Hex包"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        hex_str = ' '.join([f"{b:02X}" for b in data])
        self.ui.plainTextEdit_Debug.appendPlainText(f"[{timestamp}] {direction}: {hex_str}")
        self.ui.plainTextEdit_Debug.verticalScrollBar().setValue(
            self.ui.plainTextEdit_Debug.verticalScrollBar().maximum()
        )

    def validate_input(self):
        """验证输入"""
        if self.ui.comboBox_ID.currentIndex() == -1:
            QMessageBox.warning(self, "输入错误", "请选择模块ID")
            return False
        if self.ui.comboBox_FN.currentIndex() == -1:
            QMessageBox.warning(self, "输入错误", "请选择足编号")
            return False
        if self.ui.comboBox_MODE.currentIndex() == -1:
            QMessageBox.warning(self, "输入错误", "请选择充退磁模式")
            return False

        # 简单验证电流和时间（假设用的是QLineEdit，如果是QPlainTextEdit请用toPlainText）
        # 这里兼容处理
        try:
            current_text = self.ui.plainTextEdit_CURRENT.toPlainText().strip()
        except AttributeError:
            current_text = self.ui.plainTextEdit_CURRENT.text().strip()

        try:
            duration_text = self.ui.plainTextEdit_DURATION.toPlainText().strip()
        except AttributeError:
            duration_text = self.ui.plainTextEdit_DURATION.text().strip()

        if not current_text:
            QMessageBox.warning(self, "输入错误", "请输入电流值")
            return False
        if not duration_text:
            QMessageBox.warning(self, "输入错误", "请输入脉冲时间")
            return False

        current = int(current_text)
        duration = int(duration_text)

        if current < 0 or current > 20:
            QMessageBox.warning(self, "输入错误", "电流值必须在0-20A之间")
            return False
        if duration < 0 or duration > 30:
            QMessageBox.warning(self, "输入错误", "脉冲时间必须在0-30ms之间")
            return False
        return True

    def mag_operate(self, module_id, foot_num, mode, current, pulse_ms):
        """发送参数化命令"""
        if not self.ser.isOpen():
            self.log_message("错误：串口未打开")
            return False

        packet = bytearray()
        packet.append(0xAA)
        packet.append(0x00)
        packet.append(0x00)
        packet.append(0x04)
        packet.extend(module_id.to_bytes(4, byteorder='little'))
        packet.append(mode)
        packet.append(foot_num)
        packet.append(current)
        packet.append(pulse_ms)
        packet.extend([0x00, 0x00, 0x00, 0x00])
        packet.append(0x7A)

        try:
            self.ser.write(packet)
            self.log_message(
                f"发送命令: ID={module_id:02X}, 足={foot_num}, 模式={mode}, 电流={current}A, 时间={pulse_ms}ms")
            self.debug_message("TX", packet)
            self.module_states[module_id] = {
                "send_mode": mode, "send_foot": foot_num, "send_current": current,
                "send_pulse": pulse_ms, "recv_flag": 0, "recv_mode": 0,
                "recv_foot": 0, "recv_current": 0, "recv_pulse": 0
            }
            return True
        except Exception as e:
            self.log_message(f"发送失败: {str(e)}")
            return False

    def send_raw_hex_packet(self):
        """从Debug区域发送原始Hex"""
        if not self.ser.isOpen():
            QMessageBox.warning(self, "错误", "请先连接串口")
            return

        hex_text = self.ui.plainTextEdit_Debug.toPlainText().strip()
        if not hex_text:
            QMessageBox.information(self, "提示", "请在Debug区域输入Hex字符串")
            return

        try:
            hex_clean = re.sub(r'[\s\n]', '', hex_text)
            packet = bytes.fromhex(hex_clean)
            self.ser.write(packet)
            self.log_message(f"发送原始数据包 ({len(packet)} 字节)")
            self.debug_message("TX", packet)
        except ValueError as e:
            QMessageBox.warning(self, "Hex格式错误", f"无法解析：{str(e)}")
        except Exception as e:
            self.log_message(f"发送失败: {str(e)}")

    def receive_data(self):
        """接收并解析数据"""
        if not self.ser.isOpen():
            return
        try:
            data = self.ser.read(self.ser.in_waiting)
            if not data:
                return
            self.serial_buffer += data
        except Exception as e:
            self.log_message(f"读取错误: {str(e)}")
            return

        while len(self.serial_buffer) >= 17:
            start_idx = self.serial_buffer.find(b'\xAA')
            if start_idx == -1:
                self.serial_buffer = b""
                break
            if len(self.serial_buffer) < start_idx + 17:
                break

            frame = self.serial_buffer[start_idx:start_idx + 17]
            self.serial_buffer = self.serial_buffer[start_idx + 17:]

            if frame[-1] != 0x7A:
                self.log_message(f"无效帧: {frame.hex()}")
                continue

            self.debug_message("RX", frame)

            can_id = int.from_bytes(frame[4:8], byteorder='little')
            data_len = frame[3]
            can_data = frame[8:8 + data_len]

            if can_id >= 0x180 and can_id <= 0x1FF:
                self.parse_ack_frame(can_id - 0x180, can_data)

    def parse_ack_frame(self, module_id, data):
        """解析回执"""
        if len(data) < 5 or data[0] != 0xE0:
            return

        recv_mode = data[1]
        recv_foot = data[2]
        recv_current = data[3]
        recv_pulse = data[4]

        if module_id in self.module_states:
            self.module_states[module_id].update({
                "recv_flag": 1, "recv_mode": recv_mode, "recv_foot": recv_foot,
                "recv_current": recv_current, "recv_pulse": recv_pulse
            })

        self.log_message(f"收到回执: ID={module_id:02X}, 电流={recv_current}A")

        current_time = time.time() - self.start_time
        self.plot_time.append(current_time)
        self.plot_current.append(recv_current)
        self.plot_state.append(recv_mode)

        if len(self.plot_time) > self.max_plot_points:
            self.plot_time.pop(0)
            self.plot_current.pop(0)
            self.plot_state.pop(0)

        self.update_plots()

    def update_plots(self):
        """更新图表"""
        self.line_state.set_data(self.plot_time, self.plot_state)
        if self.plot_time:
            latest = self.plot_time[-1]
            if latest > 10:
                self.ax_state.set_xlim(latest - 10, latest)
            self.ax_state.relim()
            self.ax_state.autoscale_view(scalex=False, scaley=True)
        self.canvas_state.draw()

        self.line_current.set_data(self.plot_time, self.plot_current)
        if self.plot_time:
            latest = self.plot_time[-1]
            if latest > 10:
                self.ax_current.set_xlim(latest - 10, latest)
            self.ax_current.relim()
            self.ax_current.autoscale_view(scalex=False, scaley=True)
        self.canvas_current.draw()

    # ================= 按钮事件（保留原始结构） =================
    def on_pushButton_Connect_clicked(self):
        """连接串口"""
        self.port_open()

    def on_pushButton_Disconnect_clicked(self):
        """断开串口"""
        self.port_close()

    def on_pushButton_Begin_clicked(self):
        """Begin：图形化发送一次"""
        if not self.validate_input():
            return
        module_id = self.ui.comboBox_ID.currentData()
        foot_num = self.ui.comboBox_FN.currentData()
        mode = self.ui.comboBox_MODE.currentData()

        try:
            current = int(self.ui.plainTextEdit_CURRENT.toPlainText().strip())
            pulse = int(self.ui.plainTextEdit_DURATION.toPlainText().strip())
        except AttributeError:
            current = int(self.ui.plainTextEdit_CURRENT.text().strip())
            pulse = int(self.ui.plainTextEdit_DURATION.text().strip())

        self.mag_operate(module_id, foot_num, mode, current, pulse)

    def on_pushButton_Finish_clicked(self):
        """Finish：停止"""
        self.log_message("Finish：停止操作")

    def on_pushButton_Send_clicked(self):
        """Send：Debug区域发送原始Hex"""
        self.send_raw_hex_packet()

    def on_pushButton_Refresh_clicked(self):
        """Refresh"""
        self.port_check()
        self.log_message("Refresh：串口列表已刷新")

    def on_pushButton_Reset_clicked(self):
        """Reset"""
        self.plot_time.clear()
        self.plot_current.clear()
        self.plot_state.clear()
        self.ax_state.set_xlim(0, 10)
        self.ax_current.set_xlim(0, 10)
        self.update_plots()
        self.module_states.clear()

        try:
            self.ui.plainTextEdit_CURRENT.clear()
            self.ui.plainTextEdit_DURATION.clear()
        except:
            pass

        self.ui.plainTextEdit_Log.clear()
        self.ui.plainTextEdit_Debug.clear()

        if self.ser.isOpen():
            self.start_time = time.time()
        self.log_message("Reset：系统已重置")

    # ================= 原始串口函数（保留） =================
    def port_check(self):
        self.Com_Dict = {}
        port_list = list(serial.tools.list_ports.comports())
        print(f"[Debug] 检测到的串口数量: {len(port_list)}")
        self.ui.comboBox_DataPort.clear()
        for port in port_list:
            self.Com_Dict["%s" % port[0]] = "%s" % port[1]
            self.ui.comboBox_DataPort.addItem(port[0])
        if len(self.Com_Dict) == 0:
            pass

    def port_imf(self):
        imf_s = self.ui.comboBox_DataPort.currentText()
        if imf_s != "":
            self.ui.plainTextEdit_Log.setPlainText(self.Com_Dict[self.ui.comboBox_DataPort.currentText()])

    def port_open(self):
        self.ser.port = self.ui.comboBox_DataPort.currentText()
        print(self.ui.comboBox_DataPort.currentText())
        self.ser.baudrate = int(9600)
        self.ser.bytesize = int(8)
        self.ser.stopbits = int(1)
        self.ser.parity = "N"
        try:
            self.ser.open()
        except:
            QMessageBox.critical(self, "Port Error", "此串口不能被打开！")
        self.timer.start(5)
        self.start_time = time.time()
        if self.ser.isOpen():
            self.ui.pushButton_Connect.setEnabled(False)
            self.ui.plainTextEdit_Log.setPlainText("串口状态（已开启）")

    def port_close(self):
        self.timer.stop()
        self.timer1.stop()
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
