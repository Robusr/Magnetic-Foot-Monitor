import time
import sys
import threading
from typing import List, Optional, Sequence, Tuple
import serial
# 确保本仓库内的 unitree_sdk2py 能以“顶层包名 unitree_sdk2py”被导入（cyclonedds 解析依赖）
import os as _os
_THIS_DIR = _os.path.dirname(_os.path.abspath(__file__))
_SDK_CONTROL_DIR = _THIS_DIR  # .../go2_sdk/sdk_control
if _SDK_CONTROL_DIR not in sys.path:
    sys.path.insert(0, _SDK_CONTROL_DIR)

from unitree_sdk2py.core.channel import ChannelPublisher, ChannelSubscriber, ChannelFactoryInitialize
from unitree_sdk2py.idl.default import unitree_go_msg_dds__LowCmd_
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowCmd_, LowState_
from unitree_sdk2py.utils.crc import CRC
from unitree_sdk2py.utils.thread import RecurrentThread

from . import unitree_legged_const as go2
from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import MotionSwitcherClient
from unitree_sdk2py.go2.sport.sport_client import SportClient


class Go2LowHybrid:
    """
    最小可用封装：
    - 力位混控（LowCmd -> rt/lowcmd），内部固定频率持续发送（RecurrentThread）
    - 状态回读（LowState <- rt/lowstate）
    - 提供 set_joint / set_joints / set_all 接口更新目标
    - 提供 get_state / get_joint_state 回读

    关键：连续性来自 write 线程；你只调用 set_xxx 更新目标即可。
    """

    def __init__(self, network_interface: Optional[str] = None, hz: float = 500.0):
        # DDS init
        if network_interface:
            ChannelFactoryInitialize(0, network_interface)
        else:
            ChannelFactoryInitialize(0)

        self.hz = float(hz)
        self.dt = 1.0 / self.hz

        self.low_cmd = unitree_go_msg_dds__LowCmd_()
        self._crc = CRC()

        self.low_state: Optional[LowState_] = None
        self._lowstate_lock = threading.Lock()

        # target buffers (12 joints)
        self._tgt_lock = threading.Lock()
        self._q = [go2.PosStopF] * 12
        self._dq = [go2.VelStopF] * 12
        self._kp = [0.0] * 12
        self._kd = [0.0] * 12
        self._tau = [0.0] * 12

        # 保持姿态（用于未显式设置的关节）
        self._hold_q = [0.0] * 12
        self._hold_ready = False

        self._write_thread: Optional[RecurrentThread] = None

        self._init_lowcmd()
        self._init_channels()
        self._release_mode_until_free()

        # 等到有 lowstate，建立 hold
        self.wait_lowstate(timeout_s=2.0)
        self.set_hold_to_current()

    # -------- init helpers --------
    def mag_start(self):
        port1 = "/dev/ttyUSB0"
        baudrate = 921600
        timeout = 0.005
        # mag_on_ms = bytes.fromhex("AA 00 00 04 00 00 00" + "05" + "01" + "01" +"0E 10 00 00 00 00 7A")
        self.ser = serial.Serial(port1, baudrate, timeout=timeout)
    def mag_on(self,id):
        if id == 1:
            packet = bytes.fromhex("AA 00 00 04 00 00 00" + "31" + "02" + "01" +"0E 10 00 00 00 00 7A")
            self.ser.write(packet)
            time.sleep(0.005)
            self.ser.flush()
        elif id == 2:
            packet = bytes.fromhex("AA 00 00 04 00 00 00" + "31" + "01" + "01" +"0E 10 00 00 00 00 7A")
            self.ser.write(packet)
            time.sleep(0.005)
            self.ser.flush()
        elif id == 3:
            packet = bytes.fromhex("AA 00 00 04 00 00 00" + "35" + "02" + "01" +"0E 10 00 00 00 00 7A")
            self.ser.write(packet)
            time.sleep(0.005)
            self.ser.flush()
        elif id == 4:
            packet = bytes.fromhex("AA 00 00 04 00 00 00" + "35" + "01" + "01" +"0E 10 00 00 00 00 7A")
            self.ser.write(packet)
            time.sleep(0.005)
            self.ser.flush()
    def mag_off(self,id):
        if id ==1:
            packet = bytes.fromhex("AA 00 00 04 00 00 00" + "31" + "02" + "02" +"0E 25 00 00 00 00 7A")
            self.ser.write(packet)
            time.sleep(0.005)
            self.ser.flush()
        elif id == 2:
            packet = bytes.fromhex("AA 00 00 04 00 00 00" + "31" + "01" + "02" +"0E 25 00 00 00 00 7A")
            self.ser.write(packet)
            time.sleep(0.005)
            self.ser.flush()
        elif id == 3:
            packet = bytes.fromhex("AA 00 00 04 00 00 00" + "35" + "02" + "02" +"0E 25 00 00 00 00 7A")
            self.ser.write(packet)
            time.sleep(0.005)
            self.ser.flush()
        elif id == 4:
            packet = bytes.fromhex("AA 00 00 04 00 00 00" + "35" + "01" + "02" +"0E 25 00 00 00 00 7A")
            self.ser.write(packet)
            time.sleep(0.005)
            self.ser.flush()
    def _init_channels(self):
        self.lowcmd_publisher = ChannelPublisher("rt/lowcmd", LowCmd_)
        self.lowcmd_publisher.Init()

        self.lowstate_subscriber = ChannelSubscriber("rt/lowstate", LowState_)
        self.lowstate_subscriber.Init(self._on_lowstate, 10)

    def _release_mode_until_free(self):
        self.sc = SportClient()
        self.sc.SetTimeout(5.0)
        self.sc.Init()

        self.msc = MotionSwitcherClient()
        self.msc.SetTimeout(5.0)
        self.msc.Init()

        status, result = self.msc.CheckMode()
        while result.get("name"):
            self.sc.StandDown()
            self.msc.ReleaseMode()
            status, result = self.msc.CheckMode()
            time.sleep(1.0)

    def _init_lowcmd(self):
        # 注意：sn/version 在某些实现里是 2-byte 数组；这里不显式设置也可，
        # 但为避免你之前遇到的类型问题，用索引方式更安全。
        self.low_cmd.head[0] = 0xFE
        self.low_cmd.head[1] = 0xEF
        self.low_cmd.level_flag = 0xFF
        self.low_cmd.gpio = 0

        # 有些 IDL 带 sn/version，存在则按数组方式写
        if hasattr(self.low_cmd, "sn"):
            try:
                self.low_cmd.sn[0] = 0
                self.low_cmd.sn[1] = 0
            except Exception:
                pass
        if hasattr(self.low_cmd, "version"):
            try:
                self.low_cmd.version[0] = 0
                self.low_cmd.version[1] = 0
            except Exception:
                pass

        for i in range(20):
            self.low_cmd.motor_cmd[i].mode = 0x01
            self.low_cmd.motor_cmd[i].q = go2.PosStopF
            self.low_cmd.motor_cmd[i].dq = go2.VelStopF
            self.low_cmd.motor_cmd[i].kp = 0.0
            self.low_cmd.motor_cmd[i].kd = 0.0
            self.low_cmd.motor_cmd[i].tau = 0.0

    def _on_lowstate(self, msg: LowState_):
        with self._lowstate_lock:
            self.low_state = msg

    # -------- public: streaming control --------
    def start(self):
        """启动持续写 lowcmd 的线程（默认 500Hz）。"""
        if self._write_thread is not None:
            return
        self._write_thread = RecurrentThread(
            interval=self.dt, target=self._write_once, name="go2_lowcmd_stream"
        )
        self._write_thread.Start()

    def stop_stream(self):
        """停止持续写线程（不会自动发送 stop）。"""
        if self._write_thread is None:
            return
        self._write_thread.Stop()
        self._write_thread = None

    def close(self):
        """停止线程并发送 stop。"""
        self.stop_stream()
        self.stop()

    # -------- public: set targets --------
    def set_hold_to_current(self):
        """把当前 lowstate 的 12 关节角作为 hold 基准。"""
        st = self.get_lowstate()
        for i in range(12):
            self._hold_q[i] = float(st.motor_state[i].q)
        self._hold_ready = True

    def set_joint(self, joint_index: int, pos: float, kp: float, kd: float, vel: float = 0.0, tau: float = 0.0):
        """设置单关节目标（不会阻塞；由写线程持续发送）。"""
        i = int(joint_index)
        with self._tgt_lock:
            self._q[i] = float(pos)
            self._dq[i] = float(vel)
            self._kp[i] = float(kp)
            self._kd[i] = float(kd)
            self._tau[i] = float(tau)

    def set_joints(self, targets: dict):
        """
        批量设置多个关节：
        targets: {idx: (pos, kp, kd[, vel[, tau]])}
        """
        with self._tgt_lock:
            for idx, val in targets.items():
                i = int(idx)
                pos = float(val[0])
                kp = float(val[1])
                kd = float(val[2])
                vel = float(val[3]) if len(val) > 3 else 0.0
                tau = float(val[4]) if len(val) > 4 else 0.0
                self._q[i] = pos
                self._dq[i] = vel
                self._kp[i] = kp
                self._kd[i] = kd
                self._tau[i] = tau

    def set_all(
        self,
        q: Sequence[float],
        kp: float | Sequence[float],
        kd: float | Sequence[float],
        dq: Optional[Sequence[float]] = None,
        tau: Optional[Sequence[float]] = None,
    ):
        """一次设置 12 关节目标。"""
        if len(q) != 12:
            raise ValueError("q must be length 12")
        if dq is not None and len(dq) != 12:
            raise ValueError("dq must be length 12")
        if tau is not None and len(tau) != 12:
            raise ValueError("tau must be length 12")

        if isinstance(kp, (int, float)):
            kp_list = [float(kp)] * 12
        else:
            if len(kp) != 12:
                raise ValueError("kp must be scalar or length 12")
            kp_list = [float(x) for x in kp]

        if isinstance(kd, (int, float)):
            kd_list = [float(kd)] * 12
        else:
            if len(kd) != 12:
                raise ValueError("kd must be scalar or length 12")
            kd_list = [float(x) for x in kd]

        dq_list = [0.0] * 12 if dq is None else [float(x) for x in dq]
        tau_list = [0.0] * 12 if tau is None else [float(x) for x in tau]

        with self._tgt_lock:
            self._q = [float(x) for x in q]
            self._dq = dq_list
            self._kp = kp_list
            self._kd = kd_list
            self._tau = tau_list

    # -------- public: state --------
    def wait_lowstate(self, timeout_s: float = 2.0):
        t0 = time.time()
        while True:
            with self._lowstate_lock:
                ok = self.low_state is not None
            if ok:
                return
            if time.time() - t0 > timeout_s:
                raise RuntimeError("timeout: no rt/lowstate")
            time.sleep(0.01)

    def get_lowstate(self) -> LowState_:
        with self._lowstate_lock:
            st = self.low_state
        if st is None:
            raise RuntimeError("no lowstate yet")
        return st

    def get_joint_state(self, joint_index: int) -> Tuple[float, float]:
        st = self.get_lowstate()
        ms = st.motor_state[int(joint_index)]
        return float(ms.q), float(ms.dq)

    def get_state(self) -> dict:
        """
        返回简化状态：
        {
          "q": [12],
          "dq": [12],
          "stamp": time.time()
        }
        """
        st = self.get_lowstate()
        q = [float(st.motor_state[i].q) for i in range(12)]
        dq = [float(st.motor_state[i].dq) for i in range(12)]
        return {"q": q, "dq": dq, "stamp": time.time()}

    def get_imu(self) -> dict:
        """
        读取 GO2 的 IMU 数据（来自 rt/lowstate 的 LowState_ 消息）。
        unitree_sdk2py 的 GO2 低层状态里，IMU 通常在：
          - st.imu_state
            - quaternion: [w, x, y, z]
            - gyroscope:  [wx, wy, wz]          (rad/s)
            - accelerometer: [ax, ay, az]       (m/s^2)
            - rpy: [roll, pitch, yaw]           (rad)
            - temperature

        注意：字段命名在不同版本 SDK/IDL 里可能略有差异；这里做了兼容处理。
        """
        st = self.get_lowstate()

        # 新版（你的 unitree_sdk2py.utils.crc 打包也使用 imu_state）
        imu = getattr(st, "imu_state", None)
        if imu is not None:
            return {
                "quat": [float(imu.quaternion[i]) for i in range(4)],
                "gyro": [float(imu.gyroscope[i]) for i in range(3)],
                "acc": [float(imu.accelerometer[i]) for i in range(3)],
                "rpy": [float(imu.rpy[i]) for i in range(3)],
                "temp": float(getattr(imu, "temperature", 0.0)),
                "stamp": time.time(),
            }

        # 兼容旧字段名（如果你的某些消息生成器把字段叫 imu）
        imu = getattr(st, "imu", None)
        if imu is None:
            raise AttributeError("LowState_ has no imu_state/imu field")

        # 尽量按常见别名读取
        quat = getattr(imu, "quaternion", None)
        gyro = getattr(imu, "gyroscope", None)
        acc = getattr(imu, "accelerometer", None)

        if quat is None and hasattr(imu, "quat"):
            quat = imu.quat
        if gyro is None and hasattr(imu, "gyro"):
            gyro = imu.gyro
        if acc is None and hasattr(imu, "acc"):
            acc = imu.acc

        out = {
            "stamp": time.time(),
        }
        if quat is not None:
            out["quat"] = [float(quat[i]) for i in range(4)]
        if gyro is not None:
            out["gyro"] = [float(gyro[i]) for i in range(3)]
        if acc is not None:
            out["acc"] = [float(acc[i]) for i in range(3)]
        if hasattr(imu, "rpy"):
            out["rpy"] = [float(imu.rpy[i]) for i in range(3)]
        if hasattr(imu, "temperature"):
            out["temp"] = float(imu.temperature)
        return out
    # -------- internal write --------
    def _write_once(self):
        # 如果没 hold，用 stop 值保证安全
        if not self._hold_ready:
            return

        with self._tgt_lock:
            q = self._q[:]
            dq = self._dq[:]
            kp = self._kp[:]
            kd = self._kd[:]
            tau = self._tau[:]

        # 未设置的关节：如果还是 PosStopF，就保持 hold（避免跳）
        for i in range(12):
            mc = self.low_cmd.motor_cmd[i]
            mc.mode = 0x01

            qi = q[i]
            dqi = dq[i]
            kpi = kp[i]
            kdi = kd[i]
            taui = tau[i]

            if qi == go2.PosStopF:
                qi = self._hold_q[i]
            if dqi == go2.VelStopF:
                dqi = 0.0

            mc.q = float(qi)
            mc.dq = float(dqi)
            mc.kp = float(kpi)
            mc.kd = float(kdi)
            mc.tau = float(taui)

        self.low_cmd.crc = self._crc.Crc(self.low_cmd)
        self.lowcmd_publisher.Write(self.low_cmd)

    def stop(self):
        """发送一次 stop（kp/kd=0; PosStopF/VelStopF）。"""
        for i in range(12):
            mc = self.low_cmd.motor_cmd[i]
            mc.mode = 0x01
            mc.q = go2.PosStopF
            mc.dq = go2.VelStopF
            mc.kp = 0.0
            mc.kd = 0.0
            mc.tau = 0.0
        self.low_cmd.crc = self._crc.Crc(self.low_cmd)
        self.lowcmd_publisher.Write(self.low_cmd)


if __name__ == "__main__":
    print("WARNING: Please ensure there are no obstacles around the robot while running this example.")
    input("Press Enter to continue...")

    nic = sys.argv[1] if len(sys.argv) > 1 else None
    ctl = Go2LowHybrid(network_interface=nic, hz=500.0)
    ctl.start()

    # Demo：让 FL_0 保持当前位置 + 0.15rad
    ctl.set_hold_to_current()
    fl0 = go2.LegID["FL_0"]
    center, _ = ctl.get_joint_state(fl0)
    ctl.set_joint(fl0, pos=center + 0.15, kp=25.0, kd=2.0)

    while True:
        time.sleep(1.0)