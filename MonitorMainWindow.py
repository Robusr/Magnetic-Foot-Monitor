# 主窗口业务逻辑类
# Robusr 2026.4.19
# 2026.5.6 功能完善：串口协议对接、输入验证、模块状态管理、动态图表、日志系统
# 2026.5.6 修复：CAN ID 字节序改为小端模式(little-endian)
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
        self.serial_buffer = b""  # 串口数据接收缓冲区
        self.module_states = {}  # 磁吸附模块状态字典 {id: {状态参数}}
        self.plot_time = []  # 图表X轴（时间戳）
        self.plot_current = []  # 实际电流数据
        self.plot_state = []  # 实际状态数据（1=充磁，2=退磁）
        self.max_plot_points = 100  # 图表最大显示点数

        # === 原有代码保留，修改初始化顺序 ===
        self.port_check()
        self.init_ui_controls()  # === 初始化UI控件 ===

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.receive_data)  # === 连接到数据接收函数 ===

        # === matplotlib初始化 ===
        # 状态图表初始化
        self.figure_state = plt.figure()
        self.canvas_state = FigureCanvasQTAgg(self.figure_state)
        self.ui.gridLayout_State.addWidget(self.canvas_state, 0, 2, 2, 1)
        self.ax_state = self.canvas_state.figure.subplots(1, 1)
        self.ax_state.set_xlabel("Time (s)")
        self.ax_state.set_ylabel("State (1=Charge, 2=Discharge)")
        self.ax_state.set_ylim(0, 3)
        self.line_state, = self.ax_state.plot([], [], 'b-', label="Actual State")
        self.ax_state.legend()

        # 电流图表初始化
        self.figure_current = plt.figure()
        self.canvas_current = FigureCanvasQTAgg(self.figure_current)
        self.ui.gridLayout_Current.addWidget(self.canvas_current, 0, 2, 2, 1)
        self.ax_current = self.canvas_current.figure.subplots(1, 1)
        self.ax_current.set_xlabel("Time (s)")
        self.ax_current.set_ylabel("Current (A)")
        self.ax_current.set_ylim(0, 25)
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

    # === UI控件初始化函数 ===
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

        # === 移除 setValidator，改用信号槽实时过滤 ===
        self.ui.plainTextEdit_CURRENT.textChanged.connect(self.filter_current_input)
        self.ui.plainTextEdit_DURATION.textChanged.connect(self.filter_duration_input)

        # 默认波特率选中9600
        self.ui.comboBox_BaudRate.setCurrentText("9600")

    # === 实时过滤电流输入（只允许数字） ===
    def filter_current_input(self):
        """实时过滤电流输入框，只保留数字，并限制范围"""
        text = self.ui.plainTextEdit_CURRENT.toPlainText()
        # 只保留数字
        filtered_text = ''.join([c for c in text if c.isdigit()])

        # 如果有变化，更新文本（防止递归，先阻塞信号）
        if filtered_text != text:
            self.ui.plainTextEdit_CURRENT.blockSignals(True)
            self.ui.plainTextEdit_CURRENT.setPlainText(filtered_text)
            # 移动光标到末尾
            cursor = self.ui.plainTextEdit_CURRENT.textCursor()
            cursor.movePosition(cursor.End)
            self.ui.plainTextEdit_CURRENT.setTextCursor(cursor)
            self.ui.plainTextEdit_CURRENT.blockSignals(False)

        # 限制最大值为20
        if filtered_text:
            val = int(filtered_text)
            if val > 20:
                self.ui.plainTextEdit_CURRENT.blockSignals(True)
                self.ui.plainTextEdit_CURRENT.setPlainText("20")
                self.ui.plainTextEdit_CURRENT.blockSignals(False)

    # === 实时过滤时间输入（只允许数字） ===
    def filter_duration_input(self):
        """实时过滤时间输入框，只保留数字，并限制范围"""
        text = self.ui.plainTextEdit_DURATION.toPlainText()
        # 只保留数字
        filtered_text = ''.join([c for c in text if c.isdigit()])

        # 如果有变化，更新文本
        if filtered_text != text:
            self.ui.plainTextEdit_DURATION.blockSignals(True)
            self.ui.plainTextEdit_DURATION.setPlainText(filtered_text)
            cursor = self.ui.plainTextEdit_DURATION.textCursor()
            cursor.movePosition(cursor.End)
            self.ui.plainTextEdit_DURATION.setTextCursor(cursor)
            self.ui.plainTextEdit_DURATION.blockSignals(False)

        # 限制最大值为30
        if filtered_text:
            val = int(filtered_text)
            if val > 30:
                self.ui.plainTextEdit_DURATION.blockSignals(True)
                self.ui.plainTextEdit_DURATION.setPlainText("30")
                self.ui.plainTextEdit_DURATION.blockSignals(False)

    # === 统一日志输出函数（带时间戳） ===
    def log_message(self, message):
        """输出带时间戳的日志信息"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.ui.plainTextEdit_Log.appendPlainText(f"[{timestamp}] {message}")
        # 自动滚动到底部
        self.ui.plainTextEdit_Log.verticalScrollBar().setValue(
            self.ui.plainTextEdit_Log.verticalScrollBar().maximum()
        )

    # === 输入验证函数 ===
    def validate_input(self):
        """验证所有输入参数是否合法"""
        # 检查ID是否选择
        if self.ui.comboBox_ID.currentIndex() == -1:
            QMessageBox.warning(self, "输入错误", "请选择模块ID")
            return False

        # 检查足编号是否选择
        if self.ui.comboBox_FN.currentIndex() == -1:
            QMessageBox.warning(self, "输入错误", "请选择足编号")
            return False

        # 检查模式是否选择
        if self.ui.comboBox_MODE.currentIndex() == -1:
            QMessageBox.warning(self, "输入错误", "请选择充退磁模式")
            return False

        # 检查电流输入
        current_text = self.ui.plainTextEdit_CURRENT.toPlainText().strip()
        if not current_text:
            QMessageBox.warning(self, "输入错误", "请输入电流值")
            return False
        current = int(current_text)
        if current < 0 or current > 20:
            QMessageBox.warning(self, "输入错误", "电流值必须在0-20A之间")
            return False

        # 检查时间输入
        duration_text = self.ui.plainTextEdit_DURATION.toPlainText().strip()
        if not duration_text:
            QMessageBox.warning(self, "输入错误", "请输入脉冲时间")
            return False
        duration = int(duration_text)
        if duration < 0 or duration > 30:
            QMessageBox.warning(self, "输入错误", "脉冲时间必须在0-30ms之间")
            return False

        return True

    # === 核心命令发送函数 ===
    def mag_operate(self, module_id, foot_num, mode, current, pulse_ms):
        """
        发送磁吸附模块控制命令
        参数：
            module_id: 模块ID (1-127)
            foot_num: 足编号 (1=左腿, 2=右腿)
            mode: 模式 (1=充磁, 2=退磁)
            current: 电流值 (0-20A)
            pulse_ms: 脉冲时间 (0-30ms)
        返回：
            bool: 发送是否成功
        """
        if not self.ser.isOpen():
            self.log_message("错误：串口未打开，无法发送命令")
            return False

        # 构造串口数据包（17字节，带包尾7A）
        # 格式：AA 00 00 04 00 00 00 ID mode foot_num current pulse 00 00 00 00 7A
        packet = bytearray()
        packet.append(0xAA)  # 包首
        packet.append(0x00)  # 保留
        packet.append(0x00)  # 保留
        packet.append(0x04)  # 有效数据长度（4字节）

        # === CAN ID 改为小端模式(little-endian) ===
        packet.extend(module_id.to_bytes(4, byteorder='little'))  # 4字节CAN ID

        packet.append(mode)  # 模式
        packet.append(foot_num)  # 足编号
        packet.append(current)  # 电流值
        packet.append(pulse_ms)  # 脉冲时间
        packet.extend([0x00, 0x00, 0x00, 0x00])  # 补位
        packet.append(0x7A)  # 包尾

        try:
            self.ser.write(packet)
            self.log_message(
                f"发送命令: ID={module_id:02X}, 足={foot_num}, 模式={mode}, 电流={current}A, 时间={pulse_ms}ms")
            print(f"[Debug] 发送原始帧: {packet.hex()}")  # 新增调试打印
            # 保存发送的参数到模块状态
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

    # === 新增：串口数据接收与解析函数 ===
    def receive_data(self):
        """定时读取串口数据并解析帧"""
        if not self.ser.isOpen():
            return

        # 读取所有可用数据
        try:
            data = self.ser.read(self.ser.in_waiting)
            if not data:
                return
            self.serial_buffer += data
        except Exception as e:
            self.log_message(f"串口读取错误: {str(e)}")
            return

        # 解析完整帧（AA开头，7A结尾，长度17字节）
        while len(self.serial_buffer) >= 17:
            # 查找包首
            start_idx = self.serial_buffer.find(b'\xAA')
            if start_idx == -1:
                self.serial_buffer = b""
                break

            # 检查是否有完整帧
            if len(self.serial_buffer) < start_idx + 17:
                break

            # 提取帧
            frame = self.serial_buffer[start_idx:start_idx + 17]
            self.serial_buffer = self.serial_buffer[start_idx + 17:]

            # 验证包尾
            if frame[-1] != 0x7A:
                self.log_message(f"无效帧（包尾错误）: {frame.hex()}")
                continue

            print(f"[Debug] 收到原始帧: {frame.hex()}")  # 新增调试打印

            # === 修复：CAN ID 改为小端模式(little-endian) ===
            can_id = int.from_bytes(frame[4:8], byteorder='little')
            data_len = frame[3]
            can_data = frame[8:8 + data_len]

            # 解析回执帧（ID=0x180+模块ID）
            if can_id >= 0x180 and can_id <= 0x1FF:
                module_id = can_id - 0x180
                self.parse_ack_frame(module_id, can_data)
            else:
                self.log_message(f"收到未知CAN帧: ID={can_id:04X}, Data={can_data.hex()}")

    # === 回执帧解析函数 ===
    def parse_ack_frame(self, module_id, data):
        """解析磁吸附模块回执帧"""
        if len(data) < 5:
            self.log_message(f"回执帧长度错误: {data.hex()}")
            return

        if data[0] != 0xE0:
            self.log_message(f"无效回执标识: {data[0]:02X}")
            return

        # 提取回执参数
        recv_mode = data[1]
        recv_foot = data[2]
        recv_current = data[3]
        recv_pulse = data[4]

        # 更新模块状态
        if module_id in self.module_states:
            self.module_states[module_id]["recv_flag"] = 1
            self.module_states[module_id]["recv_mode"] = recv_mode
            self.module_states[module_id]["recv_foot"] = recv_foot
            self.module_states[module_id]["recv_current"] = recv_current
            self.module_states[module_id]["recv_pulse"] = recv_pulse

        # 输出日志
        self.log_message(
            f"收到回执: ID={module_id:02X}, 实际模式={recv_mode}, "
            f"实际足={recv_foot}, 实际电流={recv_current}A, 实际时间={recv_pulse}ms"
        )

        # 更新图表
        current_time = time.time() - self.start_time  # 相对于启动时间
        self.plot_time.append(current_time)
        self.plot_current.append(recv_current)
        self.plot_state.append(recv_mode)

        # 限制图表点数
        if len(self.plot_time) > self.max_plot_points:
            self.plot_time.pop(0)
            self.plot_current.pop(0)
            self.plot_state.pop(0)

        self.update_plots()

    # === 新增：动态更新图表函数 ===
    def update_plots(self):
        """更新状态和电流图表"""
        # 更新状态图
        self.line_state.set_data(self.plot_time, self.plot_state)
        self.ax_state.relim()
        self.ax_state.autoscale_view()
        self.canvas_state.draw()

        # 更新电流图
        self.line_current.set_data(self.plot_time, self.plot_current)
        self.ax_current.relim()
        self.ax_current.autoscale_view()
        self.canvas_current.draw()

    # === 按钮点击函数 ===
    def on_pushButton_Connect_clicked(self):
        """连接串口"""
        self.port_open()

    def on_pushButton_Disconnect_clicked(self):
        """断开串口"""
        self.port_close()

    def on_pushButton_Begin_clicked(self):
        """磁足整体启动（预留功能）"""
        self.log_message("Begin: 整体启动功能待实现")

    def on_pushButton_Finish_clicked(self):
        """磁足整体停止（预留功能）"""
        self.log_message("Finish: 整体停止功能待实现")

    def on_pushButton_Send_clicked(self):
        """发送单条控制命令"""
        if not self.validate_input():
            return

        # 获取输入参数
        module_id = self.ui.comboBox_ID.currentData()
        foot_num = self.ui.comboBox_FN.currentData()
        mode = self.ui.comboBox_MODE.currentData()
        current = int(self.ui.plainTextEdit_CURRENT.toPlainText().strip())
        pulse_ms = int(self.ui.plainTextEdit_DURATION.toPlainText().strip())

        # 发送命令
        self.mag_operate(module_id, foot_num, mode, current, pulse_ms)

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
        self.update_plots()

        # 清空模块状态
        self.module_states.clear()

        # 清空输入框
        self.ui.plainTextEdit_CURRENT.clear()
        self.ui.plainTextEdit_DURATION.clear()

        # 清空日志
        self.ui.plainTextEdit_Log.clear()

        self.start_time = time.time()  # 重置时间起点
        self.log_message("系统已重置")

    # === 原有串口检测函数，修改日志输出 ===
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

    # === 原有串口信息显示函数，修改为追加日志 ===
    def port_imf(self):
        """显示选定串口的详细信息"""
        imf_s = self.ui.comboBox_DataPort.currentText()
        if imf_s != "":
            self.log_message(f"选中串口: {self.Com_Dict[imf_s]}")

    # === 原有打开串口函数，修改波特率获取方式 ===
    def port_open(self):
        """打开串口"""
        if self.ser.isOpen():
            self.log_message("串口已打开")
            return

        port_name = self.ui.comboBox_DataPort.currentText()
        if not port_name:
            QMessageBox.critical(self, "错误", "请选择串口")
            return

        # 获取选择的波特率
        baud_rate = int(self.ui.comboBox_BaudRate.currentText())

        self.ser.port = port_name
        self.ser.baudrate = baud_rate
        self.ser.bytesize = serial.EIGHTBITS
        self.ser.stopbits = serial.STOPBITS_ONE
        self.ser.parity = serial.PARITY_NONE
        self.ser.timeout = 0.1  # 非阻塞模式

        try:
            self.ser.open()
        except Exception as e:
            QMessageBox.critical(self, "串口错误", f"无法打开串口: {str(e)}")
            self.log_message(f"串口打开失败: {str(e)}")
            return

        # 启动数据接收定时器
        self.timer.start(5)
        self.start_time = time.time()  # 记录启动时间

        # 更新UI状态
        self.ui.pushButton_Connect.setEnabled(False)
        self.ui.pushButton_Disconnect.setEnabled(True)
        self.log_message(f"串口 {port_name} 已打开，波特率 {baud_rate}")

    # === 关闭串口函数，完善状态重置 ===
    def port_close(self):
        """关闭串口"""
        self.timer.stop()
        self.serial_buffer = b""

        try:
            if self.ser.isOpen():
                self.ser.close()
        except Exception as e:
            self.log_message(f"串口关闭异常: {str(e)}")

        # 更新UI状态
        self.ui.pushButton_Connect.setEnabled(True)
        self.ui.pushButton_Disconnect.setEnabled(False)
        self.log_message("串口已关闭")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MonitorMainWindow()
    window.show()
    sys.exit(app.exec_())
