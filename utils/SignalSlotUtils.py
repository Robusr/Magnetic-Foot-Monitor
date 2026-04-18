# -*- coding: utf-8 -*-
"""
PyQt5 信号槽清理工具集
Robusr 2026.4.19
"""

from PyQt5.QtWidgets import QPushButton, QWidget
from PyQt5.QtCore import QMetaMethod, Qt


class SignalSlotCleaner:
    """信号槽清理与诊断工具"""

    @staticmethod
    def diagnose_connections(parent: QWidget, verbose: bool = True) -> dict:
        """
        诊断父控件下所有QPushButton的连接情况
        :param parent: 父窗口（通常是self）
        :param verbose: 是否打印详细信息
        :return: 包含连接信息的字典
        """
        diagnosis = {}
        buttons = parent.findChildren(QPushButton)

        if verbose:
            print(f"\n{'=' * 60}")
            print(f"🔍 信号槽连接诊断报告")
            print(f"{'=' * 60}")
            print(f"找到 {len(buttons)} 个QPushButton\n")

        for btn in buttons:
            obj_name = btn.objectName() or "未命名按钮"
            count = btn.receivers(btn.clicked)

            diagnosis[obj_name] = {
                "object": btn,
                "connection_count": count,
                "status": "✅ 正常" if count == 1 else "⚠️ 异常"
            }

            if verbose:
                status_icon = "✅" if count == 1 else "❌"
                print(f"{status_icon} {obj_name}:")
                print(f"   连接次数: {count}")
                print(f"   状态: {diagnosis[obj_name]['status']}\n")

        return diagnosis

    @staticmethod
    def clean_and_reconnect(button: QPushButton, slot_func) -> bool:
        """
        清理按钮的所有clicked连接，然后重新连接到指定槽函数
        :param button: QPushButton实例
        :param slot_func: 目标槽函数
        :return: 是否成功
        """
        btn_name = button.objectName() or "未命名按钮"

        try:
            # 1. 断开所有连接
            button.clicked.disconnect()
            print(f"🧹 已断开 [{btn_name}] 的所有连接")
        except TypeError:
            # 如果没有连接会抛出异常，这是正常的
            print(f"ℹ️ [{btn_name}] 没有已存在的连接")

        try:
            # 2. 重新连接
            button.clicked.connect(slot_func)
            new_count = button.receivers(button.clicked)
            print(f"🔗 已重新连接 [{btn_name}] -> 槽函数 (当前连接数: {new_count})")
            return True
        except Exception as e:
            print(f"❌ 连接失败 [{btn_name}]: {str(e)}")
            return False

    @staticmethod
    def auto_fix_pushbuttons(parent: QWidget, slot_mapping: dict) -> dict:
        """
        一键修复所有按钮的连接问题
        :param parent: 父窗口
        :param slot_mapping: 映射表 { "按钮objectName": 槽函数 }
        :return: 修复结果报告
        """
        results = {}

        print(f"\n{'=' * 60}")
        print(f"🔧 开始自动修复信号槽连接")
        print(f"{'=' * 60}\n")

        for btn_name, slot_func in slot_mapping.items():
            button = parent.findChild(QPushButton, btn_name)

            if not button:
                results[btn_name] = {"success": False, "error": "未找到按钮"}
                print(f"❌ 未找到按钮: {btn_name}")
                continue

            # 执行清理与重连
            success = SignalSlotCleaner.clean_and_reconnect(button, slot_func)
            results[btn_name] = {"success": success, "button": button}

        # 最终验证
        print(f"\n{'=' * 60}")
        print(f"✅ 修复完成，最终验证:")
        print(f"{'=' * 60}")
        SignalSlotCleaner.diagnose_connections(parent, verbose=True)

        return results