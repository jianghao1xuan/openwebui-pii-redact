# -*- coding: utf-8 -*-
"""六条基础检查：挡得住、重复跑不变形、还原准、不误伤。不联网、不花钱。"""
import asyncio
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _boot  # noqa: F401  （没装 pydantic 时做兜底）

sys.stdout.reconfigure(encoding="utf-8")
路 = Path(__file__).resolve().parent.parent / "filter.py"
spec = importlib.util.spec_from_file_location("filter", 路)
模块 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(模块)
F = 模块.Filter


def 跑(协程):
    return asyncio.new_event_loop().run_until_complete(协程)


def 新body(话, 场="c1"):
    return {"chat_id": 场, "messages": [{"role": "user", "content": 话}]}


身 = "11010519491231002X"     # 校验位正确
卡 = "4111111111111111"       # Luhn 正确

原文 = f"我电话 13812345678，邮箱 a.b-c@example.com，身份证 {身}，卡号 {卡}。"
坏例 = "订单号 1234567890123456789012 不该被当成卡号"

f = F()
b = 跑(f.inlet(新body(原文)))
第一次 = b["messages"][0]["content"]
print("① 脱敏后：", 第一次)
assert "13812345678" not in 第一次 and "[PHONE_1]" in 第一次
assert "a.b-c@example.com" not in 第一次 and "[EMAIL_1]" in 第一次
assert 身 not in 第一次 and "[ID_1]" in 第一次
assert 卡 not in 第一次 and "[BANK_1]" in 第一次

b2 = 跑(f.request({"chat_id": "c1", "messages": [{"role": "user", "content": 第一次}]}))
二次 = b2["messages"][0]["content"]
print("② 再跑一次：", 二次)
assert 二次 == 第一次, "重复跑不该变"

b3 = 跑(f.request({"chat_id": "c1", "messages": [{"role": "user", "content": "还有一个 13900001111"}]}))
三 = b3["messages"][0]["content"]
print("③ 第二个号：", 三)
assert "[PHONE_2]" in 三

out = 跑(f.outlet({"chat_id": "c1", "messages": [
    {"role": "assistant", "content": f"记下了 {第一次} 和 [PHONE_2]"}]}))
答 = out["messages"][0]["content"]
print("④ 还原后：", 答)
assert "13812345678" in 答 and "13900001111" in 答

f2 = F()
b4 = 跑(f2.inlet(新body(坏例, 场="c2")))
四 = b4["messages"][0]["content"]
print("⑤ 长数字串：", 四)
assert 四 == 坏例, "22 位订单号不该被当成银行卡"

f3 = F()
b5 = 跑(f3.inlet(新body("又是 13812345678", 场="c3")))
五 = b5["messages"][0]["content"]
print("⑥ 新会话：", 五)
assert "[PHONE_1]" in 五

print("\n六条全过")
