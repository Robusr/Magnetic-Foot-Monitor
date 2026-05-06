# Magnetic Foot Monitor
**磁吸附足监控上位机 **

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![PyQt5](https://img.shields.io/badge/PyQt5-5.15+-green.svg)](https://pypi.org/project/PyQt5/)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)](https://www.microsoft.com/windows)

用于控制和监控磁吸附足模块的上位机软件，支持串口通讯、实时数据可视化、原始数据包调试等功能，为磁吸附足系统设计。

## ✨ 功能特性

- 🎛️ **图形化参数配置**：直观的下拉框和输入框，快速配置模块ID、足编号、充退磁模式、电流和脉冲时间
- 🔌 **完整串口支持**：自动检测串口，支持多种波特率，完善的异常处理
- 📊 **实时数据可视化**：动态绘制实际电流和状态曲线，X轴自动滚动
- 🔧 **专业调试工具**：Debug区域支持直接输入并发送原始十六进制数据包，完整记录收发数据
- 🛡️ **输入安全验证**：实时过滤非法输入，自动限制电流(0-20A)和时间(0-30ms)范围
- 📝 **结构化日志系统**：带毫秒级时间戳的日志记录，自动滚动到底部
- 🤖 **从机模拟器**：提供纯软件从机模拟器，无需硬件即可完成全链路测试

## 🚀 快速开始

### 环境要求
- Windows 10/11
- Python 3.8 或更高版本

### 安装依赖
```bash
# 克隆仓库
git clone https://github.com/HUST-HRT/Magnetic-Foot-Monitor.git
cd Magnetic-Foot-Monitor

# 安装依赖
pip install -r requirements.txt
```

### 运行程序
```bash
python MonitorAppMain.py
```

## 📖 使用说明

### 1. 连接串口
1. 将CAN转串口模块连接到电脑
2. 在`Data Port`下拉框选择对应的串口
3. 选择波特率（默认9600）
4. 点击`Connect`按钮连接串口

### 2. 图形化控制
1. 在`Operation`区域设置参数：
   - **ID**：选择磁吸附模块ID（1-8）
   - **FN**：选择足编号（左腿/右腿）
   - **MODE**：选择工作模式（充磁/退磁）
   - **CURRENT**：输入电流值（0-20A）
   - **DURATION**：输入脉冲时间（0-30ms）
2. 点击`Begin`按钮发送一次控制命令
3. 右侧图表会实时显示实际电流和状态变化

### 3. 原始数据包调试
1. 在左侧下方的`Debug`文本框中输入十六进制字符串，例如：
   ```
   AA 00 00 04 01 00 00 00 01 01 14 0A 00 00 00 00 7A
   ```
   （支持带空格或不带空格格式）
2. 点击`Send`按钮发送原始数据包
3. Debug区域会自动显示所有收发的原始数据，用`TX:`和`RX:`区分

### 4. 数据查看
- **Actual State**图表：显示磁足的实际状态（1=充磁，2=退磁）
- **Actual Current**图表：显示实际执行的电流值
- **Log**区域：显示系统运行日志和命令执行结果

## 📁 项目结构
```
Magnetic-Foot-Monitor/
├── MonitorAppMain.py              # 程序入口
├── MonitorMainWindow.py           # 主窗口业务逻辑
├── ui_MonitorAppMainWindow.py     # 编译后的UI文件
├── res_rc.py                      # 编译后的资源文件
├── requirements.txt               # 依赖列表
├── uic.bat                        # UI文件编译脚本
├── .gitignore                     # Git忽略文件
├── README.md                      # 本文件
├── utils/
│   ├── serial_simulator.py        # 从机模拟器
│   ├── serial_util.py             # 串口工具函数
│   └── framework.py               # 通用框架代码
└── MonitorQtApp/                  # Qt C++版本（备用）
    ├── images/                    # 图片资源
    ├── main.cpp                   # C++入口
    ├── mainwindow.cpp             # C++主窗口
    ├── mainwindow.h               # C++头文件
    ├── mainwindow.ui              # Qt UI文件
    ├── res.qrc                    # Qt资源文件
    └── MonitorQtApp.pro           # Qt项目文件
```

## 📡 通讯协议

### 串口数据包格式（17字节）
| 偏移 | 长度 | 名称 | 说明 |
|------|------|------|------|
| 0 | 1 | 包首 | 固定为 `0xAA` |
| 1-2 | 2 | 保留 | 固定为 `0x00 0x00` |
| 3 | 1 | 数据长度 | CAN数据长度，控制指令为`0x04` |
| 4-7 | 4 | CAN ID | 小端模式，控制指令为模块ID |
| 8-15 | 8 | CAN数据 | 控制参数 |
| 16 | 1 | 包尾 | 固定为 `0x7A` |

### 控制指令格式（CAN数据段）
| 偏移 | 名称 | 说明 |
|------|------|------|
| 0 | mode | 1=充磁，2=退磁 |
| 1 | foot_num | 1=左腿，2=右腿 |
| 2 | current_a | 电流值（0-20A） |
| 3 | pulse_ms | 脉冲时间（0-30ms） |
| 4-7 | 保留 | 补0 |

### 回执帧格式
- CAN ID：`0x180 + 模块ID`
- 数据长度：5字节
- 数据格式：`[0xE0, mode, foot_num, current_a, pulse_ms]`

## 🤖 从机模拟器使用

### 准备工作
1. 安装虚拟串口工具 [com0com](https://github.com/hybridgroup/gobot/releases/download/v1.13.0/com0com-3.0.0.0-signed.zip)
2. 创建一对虚拟串口（例如 `COM3` <-> `COM4`）

### 运行模拟器
```bash
cd utils
python serial_simulator.py
```

### 测试流程
1. 启动模拟器，选择虚拟串口的一端（如`COM4`）
2. 启动上位机，连接另一端（如`COM3`）
3. 在上位机发送命令，模拟器会自动回复带随机误差的回执数据

## 🤝 贡献指南
1. Fork 本仓库
2. 创建你的功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交你的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开一个 Pull Request
