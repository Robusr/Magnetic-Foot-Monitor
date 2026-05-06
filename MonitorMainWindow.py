# 主窗口业务逻辑类
# Robusr 2026.4.19
# 2026.5.6 功能完善：串口协议对接、输入验证、模块状态管理、动态图表、日志系统
# 2026.5.6 修复：CAN ID 字节序改为小端模式(little-endian)
# 2026.5.6 优化：Debug区域Hex原始数据包发送、Begin/Finish手动控制
# -*- coding: utf-8 -*-
import sys
import time
import datetime
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox
from PyQt5.QtGui import QIntValidator
import serial
import serial.tools.list_ports
import re
from PyQt5.QtCore import pyqtSlot, pyqtSignal, Qt, QTimer
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

        # === 全局变量初始化 ===
        self.ser = serial.Serial()
        self.serial_buffer = b""  # 串口数据接收缓冲区（解决粘包问题）
        self.module_states = {}  # 磁吸附模块状态字典 {id: {状态参数}}
        self.plot_time = []  # 图表X轴（时间戳）
        self.plot_current = []  # 实际电流数据
        self.plot_state = []  # 实际状态数据（1=充磁，2=退磁）
        self.max_plot_points = 100  # 图表最大显示点数
        self.start_time = 0  # 串口连接时间（图表时间起点）

        # === 初始化 ===
        self.port_check()
        self.init_ui_controls()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.receive_data)

        # === 图表初始化 ===
        # 状态图表
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

        # 电流图表
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

        # 断开自动连接
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

        # 重新连接信号
        self.ui.pushButton_Connect.clicked.connect(self.on_pushButton_Connect_clicked)
        self.ui.pushButton_Disconnect.clicked.connect(self.on_pushButton_Disconnect_clicked)
        self.ui.pushButton_Begin.clicked.connect(self.on_pushButton_Begin_clicked)
        self.ui.pushButton_Finish.clicked.connect(self.on_pushButton_Finish_clicked)
        self.ui.pushButton_Send.clicked.connect(self.on_pushButton_Send_clicked)
        self.ui.pushButton_Refresh.clicked.connect(self.on_pushButton_Refresh_clicked)
        self.ui.pushButton_Reset.clicked.connect(self.on_pushButton_Reset_clicked)

        self.log_message("系统初始化完成")
        self.log_message("提示：在Debug区域输入Hex字符串(如 AA 00 00 ...)，点击下方Send发送原始包")

    def init_ui_controls(self):
        """初始化所有下拉框和输入验证器"""
        # ID下拉框（可扩展，默认1-8号节点）
        self.ui.comboBox_ID.clear()
        for i in range(1, 9):
            self.ui.comboBox_ID.addItem(f"{i:02X}", i)

        # 足编号下拉框
        self.ui.comboBox_FN.clear()
        self.ui.comboBox_FN.addItem("左腿", 1)
        self.ui.comboBox_FN.addItem("右腿", 2)

        # 模式下拉框
        self.ui.comboBox_MODE.clear()
        self.ui.comboBox_MODE.addItem("充磁", 1)
        self.ui.comboBox_MODE.addItem("退磁", 2)

        # 实时输入过滤
        self.ui.plainTextEdit_CURRENT.textChanged.connect(self.filter_current_input)
        self.ui.plainTextEdit_DURATION.textChanged.connect(self.filter_duration_input)

        # 默认波特率选中9600
        self.ui.comboBox_BaudRate.setCurrentText("9600")

    # === Debug区域原始数据包输出函数 ===
    def debug_message(self, direction, data):
        """
        在Debug区域显示原始十六进制数据包
        direction: "TX" 发送, "RX" 接收
        data: 字节数组
        """
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        hex_str = ' '.join([f"{b:02X}" for b in data])
        self.ui.plainTextEdit_Debug.appendPlainText(f"[{timestamp}] {direction}: {hex_str}")
        self.ui.plainTextEdit_Debug.verticalScrollBar().setValue(
            self.ui.plainTextEdit_Debug.verticalScrollBar().maximum()
        )

    def filter_current_input(self):
        """实时过滤电流输入框，只保留数字，并限制范围"""
        text = self.ui.plainTextEdit_CURRENT.toPlainText()
        filtered_text = ''.join([c for c in text if c.isdigit()])

        if filtered_text != text:
            self.ui.plainTextEdit_CURRENT.blockSignals(True)
            self.ui.plainTextEdit_CURRENT.setPlainText(filtered_text)
            cursor = self.ui.plainTextEdit_CURRENT.textCursor()
            cursor.movePosition(cursor.End)
            self.ui.plainTextEdit_CURRENT.setTextCursor(cursor)
            self.ui.plainTextEdit_CURRENT.blockSignals(False)

        if filtered_text:
            val = int(filtered_text)
            if val > 20:
                self.ui.plainTextEdit_CURRENT.blockSignals(True)
                self.ui.plainTextEdit_CURRENT.setPlainText("20")
                self.ui.plainTextEdit_CURRENT.blockSignals(False)

    def filter_duration_input(self):
        """实时过滤时间输入框，只保留数字，并限制范围"""
        text = self.ui.plainTextEdit_DURATION.toPlainText()
        filtered_text = ''.join([c for c in text if c.isdigit()])

        if filtered_text != text:
            self.ui.plainTextEdit_DURATION.blockSignals(True)
            self.ui.plainTextEdit_DURATION.setPlainText(filtered_text)
            cursor = self.ui.plainTextEdit_DURATION.textCursor()
            cursor.movePosition(cursor.End)
            self.ui.plainTextEdit_DURATION.setTextCursor(cursor)
            self.ui.plainTextEdit_DURATION.blockSignals(False)

        if filtered_text:
            val = int(filtered_text)
            if val > 30:
                self.ui.plainTextEdit_DURATION.blockSignals(True)
                self.ui.plainTextEdit_DURATION.setPlainText("30")
                self.ui.plainTextEdit_DURATION.blockSignals(False)

    def log_message(self, message):
        """输出带时间戳的日志信息"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.ui.plainTextEdit_Log.appendPlainText(f"[{timestamp}] {message}")
        self.ui.plainTextEdit_Log.verticalScrollBar().setValue(
            self.ui.plainTextEdit_Log.verticalScrollBar().maximum()
        )

    def validate_input(self):
        """验证所有输入参数是否合法"""
        if self.ui.comboBox_ID.currentIndex() == -1:
            QMessageBox.warning(self, "输入错误", "请选择模块ID")
            return False

        if self.ui.comboBox_FN.currentIndex() == -1:
            QMessageBox.warning(self, "输入错误", "请选择足编号")
            return False

        if self.ui.comboBox_MODE.currentIndex() == -1:
            QMessageBox.warning(self, "输入错误", "请选择充退磁模式")
            return False

        current_text = self.ui.plainTextEdit_CURRENT.toPlainText().strip()
        if not current_text:
            QMessageBox.warning(self, "输入错误", "请输入电流值")
            return False
        current = int(current_text)
        if current < 0 or current > 20:
            QMessageBox.warning(self, "输入错误", "电流值必须在0-20A之间")
            return False

        duration_text = self.ui.plainTextEdit_DURATION.toPlainText().strip()
        if not duration_text:
            QMessageBox.warning(self, "输入错误", "请输入脉冲时间")
            return False
        duration = int(duration_text)
        if duration < 0 or duration > 30:
            QMessageBox.warning(self, "输入错误", "脉冲时间必须在0-30ms之间")
            return False

        return True

    def mag_operate(self, module_id, foot_num, mode, current, pulse_ms):
        """发送磁吸附模块控制命令"""
        if not self.ser.isOpen():
            self.log_message("错误：串口未打开，无法发送命令")
            return False

        # 构造17字节数据包
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
                "send_mode": mode,
                "send_foot": foot_num,
                "send_current": current,
                "send_pulse": pulse_ms,
                "recv_flag": 0,
                "recv_mode": 0,
                "recv_foot": 0,
                "recv_current": 0,
                "recv_pulse": 0
            }
            return True
        except Exception as e:
            self.log_message(f"发送失败: {str(e)}")
            return False

    # === 新增：直接发送原始Hex数据包函数 ===
    def send_raw_hex_packet(self):
        """从Debug区域读取Hex字符串并发送"""
        if not self.ser.isOpen():
            QMessageBox.warning(self, "错误", "请先连接串口")
            return

        # 获取Debug区域的文本
        hex_text = self.ui.plainTextEdit_Debug.toPlainText().strip()

        # 如果是空的，提示用户
        if not hex_text:
            QMessageBox.information(self, "提示",
                                    "请在Debug区域输入Hex字符串，例如：\nAA 00 00 04 01 00 00 00 01 01 14 0A 00 00 00 00 7A")
            return

        try:
            # 解析Hex字符串（支持带空格或不带空格）
            # 移除所有空格和换行
            hex_clean = re.sub(r'[\s\n]', '', hex_text)
            # 转换为字节数组
            packet = bytes.fromhex(hex_clean)

            # 发送
            self.ser.write(packet)
            self.log_message(f"发送原始数据包 ({len(packet)} 字节)")
            self.debug_message("TX", packet)

        except ValueError as e:
            QMessageBox.warning(self, "Hex格式错误",
                                f"无法解析Hex字符串：{str(e)}\n\n请确保格式正确，例如：\nAA 00 00 04 ...")
        except Exception as e:
            self.log_message(f"发送失败: {str(e)}")

    def receive_data(self):
        """定时读取串口数据并解析帧"""
        if not self.ser.isOpen():
            return

        try:
            data = self.ser.read(self.ser.in_waiting)
            if not data:
                return
            self.serial_buffer += data
        except Exception as e:
            self.log_message(f"串口读取错误: {str(e)}")
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
                self.log_message(f"无效帧（包尾错误）: {frame.hex()}")
                continue

            self.debug_message("RX", frame)

            can_id = int.from_bytes(frame[4:8], byteorder='little')
            data_len = frame[3]
            can_data = frame[8:8 + data_len]

            if can_id >= 0x180 and can_id <= 0x1FF:
                module_id = can_id - 0x180
                self.parse_ack_frame(module_id, can_data)
            else:
                self.log_message(f"收到未知CAN帧: ID={can_id:04X}, Data={can_data.hex()}")

    def parse_ack_frame(self, module_id, data):
        """解析磁吸附模块回执帧"""
        if len(data) < 5:
            self.log_message(f"回执帧长度错误: {data.hex()}")
            return

        if data[0] != 0xE0:
            self.log_message(f"无效回执标识: {data[0]:02X}")
            return

        recv_mode = data[1]
        recv_foot = data[2]
        recv_current = data[3]
        recv_pulse = data[4]

        if module_id in self.module_states:
            self.module_states[module_id]["recv_flag"] = 1
            self.module_states[module_id]["recv_mode"] = recv_mode
            self.module_states[module_id]["recv_foot"] = recv_foot
            self.module_states[module_id]["recv_current"] = recv_current
            self.module_states[module_id]["recv_pulse"] = recv_pulse

        self.log_message(
            f"收到回执: ID={module_id:02X}, 实际模式={recv_mode}, "
            f"实际足={recv_foot}, 实际电流={recv_current}A, 实际时间={recv_pulse}ms"
        )

        # 更新图表
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
        """更新状态和电流图表（自动滚动X轴）"""
        # 更新状态图
        self.line_state.set_data(self.plot_time, self.plot_state)
        if self.plot_time:
            latest_time = self.plot_time[-1]
            if latest_time > 10:
                self.ax_state.set_xlim(latest_time - 10, latest_time)
            self.ax_state.relim()
            self.ax_state.autoscale_view(scalex=False, scaley=True)
        self.canvas_state.draw()

        # 更新电流图
        self.line_current.set_data(self.plot_time, self.plot_current)
        if self.plot_time:
            latest_time = self.plot_time[-1]
            if latest_time > 10:
                self.ax_current.set_xlim(latest_time - 10, latest_time)
            self.ax_current.relim()
            self.ax_current.autoscale_view(scalex=False, scaley=True)
        self.canvas_current.draw()

    # ================= 按钮点击事件处理函数 =================
    def on_pushButton_Connect_clicked(self):
        """连接串口"""
        self.port_open()

    def on_pushButton_Disconnect_clicked(self):
        """断开串口"""
        self.port_close()

    def on_pushButton_Begin_clicked(self):
        """Begin：图形化发送一次当前参数"""
        if not self.validate_input():
            return

        module_id = self.ui.comboBox_ID.currentData()
        foot_num = self.ui.comboBox_FN.currentData()
        mode = self.ui.comboBox_MODE.currentData()
        current = int(self.ui.plainTextEdit_CURRENT.toPlainText().strip())
        pulse_ms = int(self.ui.plainTextEdit_DURATION.toPlainText().strip())

        self.mag_operate(module_id, foot_num, mode, current, pulse_ms)

    def on_pushButton_Finish_clicked(self):
        """Finish：停止并清空当前状态"""
        self.log_message("Finish：停止操作")
        # 可以在这里添加停止相关的逻辑，比如发送停止命令

    def on_pushButton_Send_clicked(self):
        """Debug区域的Send：发送原始Hex数据包"""
        self.send_raw_hex_packet()

    def on_pushButton_Refresh_clicked(self):
        """刷新串口列表"""
        self.port_check()
        self.log_message("串口列表已刷新")

    def on_pushButton_Reset_clicked(self):
        """重置系统状态"""
        # 清空图表数据
        self.plot_time.clear()
        self.plot_current.clear()
        self.plot_state.clear()

        # 重置图表X轴
        self.ax_state.set_xlim(0, 10)
        self.ax_current.set_xlim(0, 10)
        self.update_plots()

        # 清空模块状态
        self.module_states.clear()

        # 清空输入框
        self.ui.plainTextEdit_CURRENT.clear()
        self.ui.plainTextEdit_DURATION.clear()

        # 清空日志和Debug
        self.ui.plainTextEdit_Log.clear()
        self.ui.plainTextEdit_Debug.clear()

        # 重置时间起点
        if self.ser.isOpen():
            self.start_time = time.time()

        self.log_message("系统已重置")

    def port_check(self):
        """检测所有存在的串口"""
        self.Com_Dict = {}
        port_list = list(serial.tools.list_ports.comports())
        self.ui.comboBox_DataPort.clear()

        for port in port_list:
            self.Com_Dict[port[0]] = port[1]
            self.ui.comboBox_DataPort.addItem(port[0])

        if len(self.Com_Dict) == 0:
            self.log_message("未检测到可用串口")
        else:
            self.log_message(f"检测到 {len(self.Com_Dict)} 个可用串口")

    def port_imf(self):
        """显示选定串口的详细信息"""
        imf_s = self.ui.comboBox_DataPort.currentText()
        if imf_s != "":
            self.log_message(f"选中串口: {self.Com_Dict[imf_s]}")

    def port_open(self):
        """打开串口"""
        if self.ser.isOpen():
            self.log_message("串口已打开")
            return

        port_name = self.ui.comboBox_DataPort.currentText()
        if not port_name:
            QMessageBox.critical(self, "错误", "请选择串口")
            return

        baud_rate = int(self.ui.comboBox_BaudRate.currentText())

        self.ser.port = port_name
        self.ser.baudrate = baud_rate
        self.ser.bytesize = serial.EIGHTBITS
        self.ser.stopbits = serial.STOPBITS_ONE
        self.ser.parity = serial.PARITY_NONE
        self.ser.timeout = 0.1

        try:
            self.ser.open()
        except Exception as e:
            QMessageBox.critical(self, "串口错误", f"无法打开串口: {str(e)}")
            self.log_message(f"串口打开失败: {str(e)}")
            return

        self.timer.start(5)
        self.start_time = time.time()

        self.ui.pushButton_Connect.setEnabled(False)
        self.ui.pushButton_Disconnect.setEnabled(True)
        self.log_message(f"串口 {port_name} 已打开，波特率 {baud_rate}")

    def port_close(self):
        """关闭串口"""
        self.timer.stop()
        self.serial_buffer = b""

        try:
            if self.ser.isOpen():
                self.ser.close()
        except Exception as e:
            self.log_message(f"串口关闭异常: {str(e)}")

        self.ui.pushButton_Connect.setEnabled(True)
        self.ui.pushButton_Disconnect.setEnabled(False)
        self.log_message("串口已关闭")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MonitorMainWindow()
    window.show()
    sys.exit(app.exec_())