# 主窗口业务逻辑类
# Robusr 2026.4.19
# 2026.5.6 最终版：保留原始断开重连机制，实现Begin图形化控制、Debug原始包发送
# 2026.5.6 修改：将Debug窗口的TX/RX原始数据包信息转移到Log窗口
# -*- coding: utf-8 -*-
import sys
import time
import datetime
import re
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox
import serial
import serial.tools.list_ports
from PyQt5.QtCore import pyqtSlot, pyqtSignal, Qt, QTimer
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

        self.ser = serial.Serial()
        self.serial_buffer = b""  # 串口接收缓冲区（解决粘包）
        self.module_states = {}  # 模块状态字典
        self.plot_time = []  # 图表X轴
        self.plot_current = []  # 实际电流数据
        self.plot_state = []  # 实际状态数据
        self.max_plot_points = 100
        self.start_time = 0  # 串口连接时间

        self.tit = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.receive_data)  # 连接数据接收函数
        self.timer1 = QTimer()

        # ================= 原始代码：第一次临时连接（必须保留） =================
        self.ui.pushButton_Connect.clicked.connect(self.port_open)
        self.ui.pushButton_Disconnect.clicked.connect(self.port_close)
        self.ui.comboBox_DataPort.currentTextChanged.connect(self.port_imf)
        # =====================================================================

        # 图表初始化（替换原始的x²测试曲线）
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

        # ================= 原始代码：断开所有自动连接（必须完整保留） =================
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
        # =====================================================================

        # ================= 原始代码：手动重新连接（必须保留结构） =================
        self.ui.pushButton_Connect.clicked.connect(self.on_pushButton_Connect_clicked)
        self.ui.pushButton_Disconnect.clicked.connect(self.on_pushButton_Disconnect_clicked)

        self.ui.pushButton_Begin.clicked.connect(self.on_pushButton_Begin_clicked)
        self.ui.pushButton_Finish.clicked.connect(self.on_pushButton_Finish_clicked)

        self.ui.pushButton_Send.clicked.connect(self.on_pushButton_Send_clicked)
        self.ui.pushButton_Refresh.clicked.connect(self.on_pushButton_Refresh_clicked)
        self.ui.pushButton_Reset.clicked.connect(self.on_pushButton_Reset_clicked)
        # =====================================================================

        # 初始化UI控件和串口
        self.init_ui_controls()
        self.port_check()
        self.log_message("系统初始化完成")
        self.log_message("使用说明：")
        self.log_message("1. Begin按钮：发送一次左侧设置的参数化命令")
        self.log_message("2. 在下方Debug区域输入Hex字符串，点击Send发送原始数据包")

    # ================= 新增：UI初始化函数 =================
    def init_ui_controls(self):
        """初始化下拉框选项"""
        # ID下拉框（1-8号节点）
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

        # 默认波特率9600
        self.ui.comboBox_BaudRate.setCurrentText("9600")

    # ================= 日志输出函数（统一输出到Log窗口） =================
    def log_message(self, message):
        """带时间戳的日志输出（所有信息统一输出到Log窗口）"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.ui.plainTextEdit_Log.appendPlainText(f"[{timestamp}] {message}")
        # 自动滚动到底部
        self.ui.plainTextEdit_Log.verticalScrollBar().setValue(
            self.ui.plainTextEdit_Log.verticalScrollBar().maximum()
        )

    # ================= 修改：原始数据包信息输出到Log窗口 =================
    def debug_message(self, direction, data):
        """原始Hex数据包信息输出到Log窗口"""
        hex_str = ' '.join([f"{b:02X}" for b in data])
        self.log_message(f"{direction}: {hex_str}")

    # ================= 新增：输入验证函数 =================
    def validate_input(self):
        """验证所有输入参数合法性"""
        if self.ui.comboBox_ID.currentIndex() == -1:
            QMessageBox.warning(self, "输入错误", "请选择模块ID")
            return False
        if self.ui.comboBox_FN.currentIndex() == -1:
            QMessageBox.warning(self, "输入错误", "请选择足编号")
            return False
        if self.ui.comboBox_MODE.currentIndex() == -1:
            QMessageBox.warning(self, "输入错误", "请选择充退磁模式")
            return False

        # 获取输入值（兼容QPlainTextEdit）
        current_text = self.ui.plainTextEdit_CURRENT.toPlainText().strip()
        duration_text = self.ui.plainTextEdit_DURATION.toPlainText().strip()

        if not current_text:
            QMessageBox.warning(self, "输入错误", "请输入电流值")
            return False
        if not duration_text:
            QMessageBox.warning(self, "输入错误", "请输入脉冲时间")
            return False

        try:
            current = int(current_text)
            duration = int(duration_text)
        except ValueError:
            QMessageBox.warning(self, "输入错误", "电流和时间必须为整数")
            return False

        if current < 0 or current > 20:
            QMessageBox.warning(self, "输入错误", "电流值必须在0-20A之间")
            return False
        if duration < 0 or duration > 30:
            QMessageBox.warning(self, "输入错误", "脉冲时间必须在0-30ms之间")
            return False

        return True

    # ================= 新增：参数化命令发送函数 =================
    def mag_operate(self, module_id, foot_num, mode, current, pulse_ms):
        """发送标准磁吸附控制命令"""
        if not self.ser.isOpen():
            self.log_message("错误：串口未打开，无法发送命令")
            return False

        # 构造17字节标准数据包（小端CAN ID）
        packet = bytearray()
        packet.append(0xAA)  # 包首
        packet.append(0x00)  # 保留
        packet.append(0x00)  # 保留
        packet.append(0x04)  # 有效数据长度
        packet.extend(module_id.to_bytes(4, byteorder='little'))  # CAN ID（小端）
        packet.append(mode)  # 模式：1=充磁，2=退磁
        packet.append(foot_num)  # 足编号：1=左腿，2=右腿
        packet.append(current)  # 电流值(A)
        packet.append(pulse_ms)  # 脉冲时间(ms)
        packet.extend([0x00, 0x00, 0x00, 0x00])  # 补位
        packet.append(0x7A)  # 包尾

        try:
            self.ser.write(packet)
            self.log_message(
                f"发送命令: ID={module_id:02X}, 足={foot_num}, 模式={mode}, 电流={current}A, 时间={pulse_ms}ms")
            self.debug_message("TX", packet)

            # 保存发送状态
            self.module_states[module_id] = {
                "send_mode": mode,
                "send_foot": foot_num,
                "send_current": current,
                "send_pulse": pulse_ms,
                "recv_flag": 0
            }
            return True
        except Exception as e:
            self.log_message(f"发送失败: {str(e)}")
            return False

    # ================= 新增：原始Hex数据包发送函数 =================
    def send_raw_hex_packet(self):
        """从Debug区域读取Hex字符串并发送原始数据包"""
        if not self.ser.isOpen():
            QMessageBox.warning(self, "错误", "请先连接串口")
            return

        hex_text = self.ui.plainTextEdit_Debug.toPlainText().strip()
        if not hex_text:
            QMessageBox.information(self, "提示",
                                    "请在Debug区域输入十六进制字符串\n例如：AA 00 00 04 01 00 00 00 01 01 14 0A 00 00 00 00 7A")
            return

        try:
            # 移除所有空格和换行
            hex_clean = re.sub(r'[\s\n]', '', hex_text)
            # 转换为字节数组
            packet = bytes.fromhex(hex_clean)

            self.ser.write(packet)
            self.log_message(f"发送原始数据包 ({len(packet)} 字节)")
            self.debug_message("TX", packet)

        except ValueError as e:
            QMessageBox.warning(self, "Hex格式错误", f"无法解析输入：{str(e)}\n请确保只包含0-9和A-F字符")
        except Exception as e:
            self.log_message(f"发送失败: {str(e)}")

    # ================= 新增：串口数据接收与解析函数 =================
    def receive_data(self):
        """定时读取串口数据并解析帧"""
        if not self.ser.isOpen():
            return

        try:
            # 读取所有可用数据
            data = self.ser.read(self.ser.in_waiting)
            if not data:
                return
            self.serial_buffer += data
        except Exception as e:
            self.log_message(f"串口读取错误: {str(e)}")
            return

        # 循环解析缓冲区中的完整帧
        while len(self.serial_buffer) >= 17:
            # 查找包首0xAA
            start_idx = self.serial_buffer.find(b'\xAA')
            if start_idx == -1:
                self.serial_buffer = b""
                break

            # 检查是否有完整的17字节帧
            if len(self.serial_buffer) < start_idx + 17:
                break

            # 提取一帧数据
            frame = self.serial_buffer[start_idx:start_idx + 17]
            self.serial_buffer = self.serial_buffer[start_idx + 17:]

            # 验证包尾
            if frame[-1] != 0x7A:
                self.log_message(f"无效帧（包尾错误）: {frame.hex()}")
                continue

            # 输出到Log窗口
            self.debug_message("RX", frame)

            # 解析CAN ID（小端模式）
            can_id = int.from_bytes(frame[4:8], byteorder='little')
            data_len = frame[3]
            can_data = frame[8:8 + data_len]

            # 解析回执帧（ID=0x180+模块ID）
            if can_id >= 0x180 and can_id <= 0x1FF:
                module_id = can_id - 0x180
                self.parse_ack_frame(module_id, can_data)
            else:
                self.log_message(f"收到未知CAN帧: ID={can_id:04X}, Data={can_data.hex()}")

    # ================= 新增：回执帧解析函数 =================
    def parse_ack_frame(self, module_id, data):
        """解析从机返回的执行状态回执"""
        if len(data) < 5 or data[0] != 0xE0:
            return

        recv_mode = data[1]
        recv_foot = data[2]
        recv_current = data[3]
        recv_pulse = data[4]

        # 更新模块状态
        if module_id in self.module_states:
            self.module_states[module_id].update({
                "recv_flag": 1,
                "recv_mode": recv_mode,
                "recv_foot": recv_foot,
                "recv_current": recv_current,
                "recv_pulse": recv_pulse
            })

        self.log_message(
            f"收到回执: ID={module_id:02X}, 实际模式={recv_mode}, "
            f"实际足={recv_foot}, 实际电流={recv_current}A, 实际时间={recv_pulse}ms"
        )

        # 更新图表数据
        current_time = time.time() - self.start_time
        self.plot_time.append(current_time)
        self.plot_current.append(recv_current)
        self.plot_state.append(recv_mode)

        # 限制图表最大点数
        if len(self.plot_time) > self.max_plot_points:
            self.plot_time.pop(0)
            self.plot_current.pop(0)
            self.plot_state.pop(0)

        self.update_plots()

    # ================= 新增：图表更新函数 =================
    def update_plots(self):
        """实时更新状态和电流图表"""
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

    # ================= 按钮点击事件（保留原始函数名） =================
    def on_pushButton_Connect_clicked(self):
        """连接串口"""
        self.port_open()

    def on_pushButton_Disconnect_clicked(self):
        """断开串口"""
        self.port_close()

    def on_pushButton_Begin_clicked(self):
        """Begin：图形化发送一次当前设置的参数"""
        if not self.validate_input():
            return

        module_id = self.ui.comboBox_ID.currentData()
        foot_num = self.ui.comboBox_FN.currentData()
        mode = self.ui.comboBox_MODE.currentData()
        current = int(self.ui.plainTextEdit_CURRENT.toPlainText().strip())
        pulse_ms = int(self.ui.plainTextEdit_DURATION.toPlainText().strip())

        self.mag_operate(module_id, foot_num, mode, current, pulse_ms)

    def on_pushButton_Finish_clicked(self):
        """Finish：停止操作（预留扩展）"""
        self.log_message("Finish：停止操作")

    def on_pushButton_Send_clicked(self):
        """Send：发送Debug区域的原始Hex数据包"""
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
        self.ax_state.set_xlim(0, 10)
        self.ax_current.set_xlim(0, 10)
        self.update_plots()

        # 清空模块状态
        self.module_states.clear()

        # 清空输入框
        self.ui.plainTextEdit_CURRENT.clear()
        self.ui.plainTextEdit_DURATION.clear()
        self.ui.plainTextEdit_Debug.clear()  # 保留清空Debug输入框

        # 清空日志
        self.ui.plainTextEdit_Log.clear()

        # 重置时间起点
        if self.ser.isOpen():
            self.start_time = time.time()

        self.log_message("系统已重置")

    # ================= 原始串口函数（100%保留未修改） =================
    def port_check(self):
        # 检测所有存在的串口，将信息存储在字典中
        self.Com_Dict = {}  # 创建一个字典，字典是可变的容器
        port_list = list(serial.tools.list_ports.comports())  # list是序列，一串数据，可以追加数据

        print(f"[Debug] 检测到的串口数量: {len(port_list)}")

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
        self.start_time = time.time()  # 记录串口连接时间
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