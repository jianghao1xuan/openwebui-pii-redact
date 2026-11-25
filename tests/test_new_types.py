# -*- coding: utf-8 -*-
"""后补的四类：固话、车牌、统一社会信用代码、护照。不联网、不花钱。"""
import asyncio
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _boot  # noqa: F401  （没装 pydantic 时做兜底）

sys.stdout.reconfigure(encoding="utf-8")
spec = importlib.util.spec_from_file_location("filter", Path(__file__).resolve().parent.parent / "filter.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
F = m.Filter


def 跑(c):
    return asyncio.new_event_loop().run_until_complete(c)


应挡 = [
    ("固话区号横杠", "0571-88888888"),
    ("固话带括号", "(010) 12345678"),
    ("400 电话", "400-123-4567"),
    ("车牌普通", "京A12345"),
    ("车牌新能源", "粤BD12345"),
    ("统一社会信用代码", "91350100M000100Y43"),
    ("护照 E", "E12345678"),
    ("护照 G", "G87654321"),
]
不该 = [
    "订单 20261124001",
    "价格 4111 元",
    "日期 2026-11-24",
    "时间 14:35",
    "年份 1949 到 2026",
    "编号 A1234567",
    "京A123456",        # 8 位、字母后不是 D/F：不是车牌，别吃
]

f = F()
好 = 0
for 名, 值 in 应挡:
    b = 跑(f.inlet({"chat_id": "n1", "messages": [{"role": "user", "content": f"这是：{值} 完"}]}))
    出 = b["messages"][0]["content"]
    挡 = 值 not in 出
    回 = 跑(f.outlet({"chat_id": "n1", "messages": [{"role": "assistant", "content": 出}]}))["messages"][0]["content"]
    精确 = 回 == f"这是：{值} 完"
    print(("✓" if 挡 else "✗"), 名, "→", 出[:34], "| 还原", 精确)
    好 += 1 if (挡 and 精确) else 0

print()
错 = 0
for 值 in 不该:
    b = 跑(f.inlet({"chat_id": "n2", "messages": [{"role": "user", "content": 值}]}))
    变 = b["messages"][0]["content"] != 值
    错 += 1 if 变 else 0
    print("  ✗ 误伤" if 变 else "  不动", 值)

print(f"\n应挡 {好}/{len(应挡)}｜误伤 {错}/{len(不该)}")
assert 好 == len(应挡) and 错 == 0
