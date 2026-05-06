import serial
import serial.tools.list_ports

print("=== 系统串口检测结果 ===")
ports = serial.tools.list_ports.comports()
print(f"检测到的串口总数: {len(ports)}")

for port in ports:
    print(f"\n端口号: {port.device}")
    print(f"描述: {port.description}")
    print(f"硬件ID: {port.hwid}")
    print(f"制造商: {port.manufacturer}")