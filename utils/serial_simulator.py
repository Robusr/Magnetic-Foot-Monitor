import serial
import time
import random
import struct

# ================= 配置区域 =================
# 请修改为你 com0com 创建的另一端串口（如果主程序用 COM3，这里用 COM4）
VIRTUAL_SERIAL_PORT = 'COM4'
BAUD_RATE = 921600


# ===========================================

class MagFootSlaveSimulator:
    """磁吸附模块从机模拟器"""

    def __init__(self, port, baudrate):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.serial_buffer = b""  # 数据接收缓冲区（处理粘包）

    def connect(self):
        """连接虚拟串口"""
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1
            )
            print(f" 虚拟串口 {self.port} 已打开，波特率 {self.baudrate}")
            print("=" * 60)
            print("等待接收主机命令...")
            return True
        except Exception as e:
            print(f" 串口打开失败: {e}")
            print("请检查：1. 串口号是否正确；2. 串口是否被占用")
            return False

    def parse_host_frame(self, frame):
        """
        解析主机发来的 17 字节数据包
        返回: (module_id, mode, foot_num, current, pulse_ms)
        """
        # 1. 验证包首和包尾
        if frame[0] != 0xAA or frame[-1] != 0x7A:
            raise ValueError("包首或包尾错误")

        # 2. 提取 CAN ID (4字节)
        # === 修复：改为小端模式(little-endian) ===
        can_id_bytes = frame[4:8]
        can_id = int.from_bytes(can_id_bytes, byteorder='little')
        module_id = can_id  # 对于主机发的包，CAN ID 直接等于模块 ID

        # 3. 提取有效数据长度
        data_len = frame[3]
        if data_len != 0x04:
            raise ValueError(f"数据长度错误，期望0x04，实际{data_len:02X}")

        # 4. 提取控制数据 (d[0]~d[3])
        mode = frame[8]  # 1=充磁, 2=退磁
        foot_num = frame[9]  # 1=左腿, 2=右腿
        current = frame[10]  # 电流值 (A)
        pulse_ms = frame[11]  # 脉冲时间 (ms)

        return module_id, mode, foot_num, current, pulse_ms

    def build_ack_frame(self, module_id, mode, foot_num, current, pulse_ms):
        """
        构造从机回执数据包 (17字节)
        协议: CAN ID = 0x180 + module_id
        """
        packet = bytearray()

        # 1. 包首
        packet.append(0xAA)

        # 2. 保留字节
        packet.extend([0x00, 0x00])

        # 3. 有效数据长度 (回执是5个字节: E0 + mode + foot + current + pulse)
        packet.append(0x05)

        # 4. CAN ID (4字节)
        # === 修复：改为小端模式(little-endian) ===
        ack_can_id = 0x180 + module_id
        packet.extend(ack_can_id.to_bytes(4, byteorder='little'))

        # 5. 回执数据
        packet.append(0xE0)  # 回执固定标识
        packet.append(mode)  # 实际执行模式 (原样返回)
        packet.append(foot_num)  # 实际执行足号 (原样返回)

        # 模拟真实硬件：电流可能有 ±1A 的误差，且限制在 0-20A
        actual_current = current + random.randint(-1, 1)
        actual_current = max(0, min(20, actual_current))
        packet.append(actual_current)

        packet.append(pulse_ms)  # 实际执行时间 (原样返回)

        # 6. 补位 (填充到16字节数据段)
        packet.extend([0x00, 0x00, 0x00])

        # 7. 包尾
        packet.append(0x7A)

        return packet, actual_current

    def run(self):
        """主运行循环"""
        if not self.ser or not self.ser.is_open:
            return

        try:
            while True:
                # 1. 读取所有可用数据
                if self.ser.in_waiting > 0:
                    data = self.ser.read(self.ser.in_waiting)
                    self.serial_buffer += data

                # 2. 循环解析缓冲区中的完整帧
                while len(self.serial_buffer) >= 17:
                    # 查找包首 0xAA
                    start_idx = self.serial_buffer.find(b'\xAA')

                    if start_idx == -1:
                        # 没找到包首，清空缓冲区
                        self.serial_buffer = b""
                        break

                    if start_idx > 0:
                        # 丢弃包首之前的垃圾数据
                        print(f" 丢弃垃圾数据: {self.serial_buffer[:start_idx].hex()}")
                        self.serial_buffer = self.serial_buffer[start_idx:]

                    # 检查是否有完整的 17 字节
                    if len(self.serial_buffer) < 17:
                        break  # 数据不够，等下次

                    # 提取一帧
                    frame = self.serial_buffer[:17]
                    # 从缓冲区移除已处理的帧
                    self.serial_buffer = self.serial_buffer[17:]

                    # 3. 解析并处理这一帧
                    try:
                        module_id, mode, foot_num, current, pulse = self.parse_host_frame(frame)

                        # 打印收到的命令
                        mode_str = "充磁" if mode == 1 else "退磁" if mode == 2 else "未知"
                        foot_str = "左腿" if foot_num == 1 else "右腿" if foot_num == 2 else "未知"

                        print("-" * 60)
                        print(f"   收到主机命令:")
                        print(f"   模块ID: {module_id:02X}")
                        print(f"   模式:   {mode} ({mode_str})")
                        print(f"   足号:   {foot_num} ({foot_str})")
                        print(f"   电流:   {current} A")
                        print(f"   时间:   {pulse} ms")
                        print(f"   原始帧: {frame.hex()}")

                        # 4. 构造并发送回执
                        ack_frame, actual_current = self.build_ack_frame(
                            module_id, mode, foot_num, current, pulse
                        )

                        # 模拟硬件处理延迟 (50ms)
                        time.sleep(0.05)

                        self.ser.write(ack_frame)

                        print(f"   发送从机回执:")
                        print(f"   实际电流: {actual_current} A (已模拟误差)")
                        print(f"   原始帧:   {ack_frame.hex()}")

                    except ValueError as e:
                        print(f"  帧解析错误: {e}, 数据: {frame.hex()}")

                time.sleep(0.01)  # 避免CPU占用过高

        except KeyboardInterrupt:
            print("\n  模拟器已停止")
        finally:
            if self.ser and self.ser.is_open:
                self.ser.close()

# 模块启动函数
if __name__ == '__main__':
    print("=" * 60)
    print("   磁吸附模块 - 从机模拟器 (Magnetic Foot Slave Simulator)")
    print("=" * 60)

    simulator = MagFootSlaveSimulator(VIRTUAL_SERIAL_PORT, BAUD_RATE)

    if simulator.connect():
        simulator.run()
