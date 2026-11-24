# -*- coding: utf-8 -*-
"""工具版自测：txt / csv 两条线，预览、脱敏、还原。"""
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
根 = Path(__file__).resolve().parent.parent
工具 = 根 / "tool" / "pii_tool.py"
Py = sys.executable
临 = Path(tempfile.mkdtemp(prefix="pii_tool_"))

def 跑(*参):
    r = subprocess.run([Py, str(工具), *map(str, 参)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, r.stdout + r.stderr

# 1) txt
样本 = 临 / "客户.txt"
原文 = "张伟 13812345678\n李娜 +86 139-0000-2222\n固话 0571-88888888 车牌 京A12345\n"
样本.write_text(原文, encoding="utf-8")

码, 出 = 跑("preview", 样本)
print("== preview ==")
print(出.strip())

码, 出 = 跑("redact", 样本)
print("\n== redact ==")
print(出.strip())
脱敏 = 样本.with_name("客户.redacted.txt")
映射 = 样本.with_name("客户.map.json")
print("脱敏后内容：")
print(脱敏.read_text(encoding="utf-8"))

# 2) 还原
码, 出 = 跑("restore", 脱敏, "--map", 映射)
还原 = 脱敏.with_name("客户.redacted.restored.txt")
print("== restore ==", 出.strip())
print("还原一致：", 还原.read_text(encoding="utf-8") == 原文)

# 3) csv
表 = 临 / "客户.csv"
表.write_text("姓名,手机,订单\n张伟,13812345678,20261124001\n李娜,13900002222,20261124002\n",
              encoding="utf-8-sig")
码, 出 = 跑("redact", 表)
print("\n== csv redact ==")
print(出.strip())
print(表.with_name("客户.redacted.csv").read_text(encoding="utf-8-sig"))
