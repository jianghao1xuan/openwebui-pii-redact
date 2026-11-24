# -*- coding: utf-8 -*-
"""八种写法都要挡，且还原逐字一致；四种正常文字不许动。不联网、不花钱。"""
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


例 = [
    ("手机 +86 空格", "+86 138 0000 6666"),
    ("手机横杠", "138-0000-7777"),
    ("手机纯数字", "13812345678"),
    ("卡号分段", "4111 1111 1111 1111"),
    ("卡号横杠", "4111-1111-1111-1111"),
    ("身份证 18 位", "11010519491231002X"),
    ("15 位老身份证", "110105491231003"),
    ("邮箱", "zhang.san+tag@sub.example.com"),
]

f = F()
好 = 0
for 名, 值 in 例:
    b = 跑(f.inlet({"chat_id": "v", "messages": [{"role": "user", "content": f"值：{值}。说完了"}]}))
    出 = b["messages"][0]["content"]
    挡 = 值 not in 出
    回 = 跑(f.outlet({"chat_id": "v", "messages": [{"role": "assistant", "content": 出}]}))["messages"][0]["content"]
    精确 = 回 == f"值：{值}。说完了"
    print(("✓" if 挡 else "✗"), 名, "→", 出[:40], "| 还原精确", 精确)
    好 += 1 if (挡 and 精确) else 0

不该 = ["订单号 20261124001", "价格 4111 元", "年份 1949 到 2026"]
print()
for 值 in 不该:
    b = 跑(f.inlet({"chat_id": "v2", "messages": [{"role": "user", "content": 值}]}))
    print("  不动" if b["messages"][0]["content"] == 值 else "  ✗ 误伤", 值)

print(f"\n变体 {好}/{len(例)} 全过")
assert 好 == len(例)
