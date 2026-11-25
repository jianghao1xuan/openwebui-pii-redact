# -*- coding: utf-8 -*-
"""验并发：两个会话同时跑时，流式块不许拿别人的映射还原。"""
import asyncio
import importlib.util
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
路 = Path(__file__).resolve().parent.parent / "filter.py"
spec = importlib.util.spec_from_file_location("f", 路)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
F = m.Filter


def 跑(c):
    return asyncio.new_event_loop().run_until_complete(c)


def 块(文):
    return {"choices": [{"delta": {"content": 文}}]}


f = F()

# 两个会话各自发一句，各含不同号码
跑(f.inlet({"chat_id": "A", "messages": [{"role": "user", "content": "我号 13811112222"}]}))
跑(f.inlet({"chat_id": "B", "messages": [{"role": "user", "content": "我号 13933334444"}]}))

print("A 的映射：", f._场("A")["map"])
print("B 的映射：", f._场("B")["map"])

# 现在两个场都活着，流式块没有 chat_id
出 = 跑(f.stream(块("你的号是 [PHONE_1]")))
内容 = 出["choices"][0]["delta"]["content"]
print("\n两个会话同时活着时，无 chat_id 的块：", 内容)
print("  有没有被换错人：", ("13811112222" in 内容) or ("13933334444" in 内容))
好1 = 内容 == "你的号是 [PHONE_1]"

# 只剩一个场活着（把 B 的时间推回去）
f._场("B")["at"] = 0
出2 = 跑(f.stream(块("你的号是 [PHONE_1]")))
内容2 = 出2["choices"][0]["delta"]["content"]
print("\n只剩 A 活着时：", 内容2)
好2 = 内容2 == "你的号是 13811112222"

print("\n结论：", "过" if (好1 and 好2) else "没过")
sys.exit(0 if (好1 and 好2) else 1)
