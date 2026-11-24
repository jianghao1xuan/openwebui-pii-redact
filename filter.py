"""
title: 脱敏（手机号 / 身份证 / 银行卡 / 邮箱）
author: jianghao1xuan
version: 0.1.0
description: 这一版只覆盖八类有规则的写法，处理过的内容请复核一遍。发出去之前把中文敏感信息换成占位符，回复到界面前再还原。映射只存内存。
required_open_webui_version: 0.9.0
"""

import hashlib
import json
import re
import threading
import time
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

import tempfile



class Filter:
    class Valves(BaseModel):
        # 排查用：默认不写盘。要看来回的样子，把 log_payload 打开、log_dir 指个目录。
        log_payload: bool = False
        log_dir: str = ""
        mask_phone: bool = True
        mask_id: bool = True
        mask_bank: bool = True
        mask_email: bool = True
        mask_tel: bool = True
        mask_plate: bool = True
        mask_uscc: bool = True
        mask_passport: bool = True
        restore: bool = True

    def __init__(self):
        self.valves = self.Valves()
        self.toggle = False          # 管理员全局开着就行，不交给用户关
        self._锁 = threading.Lock()
        # 每场对话一份：{chat_id: {"n": {"PHONE": 2}, "map": {"[PHONE_1]": "138..."}}}
        self._每场 = {}
        self._最大场数 = 200

    # ---------- 正则 ----------
    # 手机：1 开头 11 位，前后不能再是数字
    _手机 = re.compile(r"(?<![\d])(?:\+?86[\s\-]?)?1[3-9](?:[\s\-]?\d){9}(?!\d)")
    # 身份证：18 位，最后一位可为 X（还会过校验位）
    _身份证 = re.compile(r"(?<![\d])\d{6}(?:[\s\-]?\d){11}[\dXx](?![\d])")
    # 老身份证 15 位（没有校验位，只验日期）
    _身份证15 = re.compile(r"(?<![\d])\d{6}(?:[\s\-]?\d){9}(?![\d])")
    # 银行卡：16-19 位连续数字（还会过 Luhn）
    _银行卡 = re.compile(r"(?<![\d])\d{4}(?:[\s\-]?\d){12,15}(?![\d])")
    _邮箱 = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
    # 固话：区号(3-4 位，0 开头) + 7-8 位号码，可带括号和横杠
    _固话 = re.compile(r"(?<![\d])(?:\(0\d{2,3}\)|0\d{2,3})[\s\-]?\d{7,8}(?![\d])")
    # 400 / 800 电话
    _客服电话 = re.compile(r"(?<![\d])(?:400|800)[\s\-]?\d{3}[\s\-]?\d{4}(?![\d])")
    # 车牌：省简称 + 字母 + 5 位（新能源 6 位）
    _车牌 = re.compile(
        r"(?<![A-Za-z0-9\u4e00-\u9fa5])"
        r"[京津冀晋蒙辽吉黑沪苏浙皖闽赣鲁豫鄂湘粤桂琼渝川贵云藏陕甘青宁新]"
        r"[A-HJ-NP-Z][A-HJ-NP-Z0-9]{4,5}[A-HJ-NP-Z0-9挂学警港澳]"
        r"(?![A-Za-z0-9])")
    # 统一社会信用代码：18 位，字符集不含 I O S V Z
    _统一代码 = re.compile(r"(?<![0-9A-Z])[0-9A-HJ-NPQRTUWXY]{2}\d{6}[0-9A-HJ-NPQRTUWXY]{10}(?![0-9A-Z])")
    # 护照：E/G + 8 位数字
    _护照 = re.compile(r"(?<![0-9A-Za-z])[EG]\d{8}(?![0-9A-Za-z])")

    # ---------- 校验 ----------
    @staticmethod
    def _身份证对(号: str) -> bool:
        权 = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
        码 = "10X98765432"
        try:
            和 = sum(int(号[i]) * 权[i] for i in range(17))
        except ValueError:
            return False
        return 码[和 % 11] == 号[17].upper()

    @staticmethod
    def _统一代码对(码: str) -> bool:
        字 = "0123456789ABCDEFGHJKLMNPQRTUWXY"
        权 = (1, 3, 9, 27, 19, 26, 16, 17, 20, 29, 25, 13, 8, 24, 10, 30, 28)
        try:
            和 = sum(字.index(码[i]) * 权[i] for i in range(17))
        except ValueError:
            return False
        应 = 字[(31 - 和 % 31) % 31]
        return 码[17] == 应

    @staticmethod
    def _银行卡对(号: str) -> bool:
        总 = 0
        for i, ch in enumerate(reversed(号)):
            数 = int(ch)
            if i % 2 == 1:
                数 *= 2
                if 数 > 9:
                    数 -= 9
            总 += 数
        return 总 % 10 == 0

    # ---------- 状态 ----------
    def _场(self, 键: str) -> dict:
        with self._锁:
            if 键 not in self._每场:
                if len(self._每场) >= self._最大场数:
                    self._每场.pop(next(iter(self._每场)))
                self._每场[键] = {"n": {}, "map": {}, "键": {}}
            return self._每场[键]

    def _重置(self, 键: str) -> None:
        with self._锁:
            self._每场[键] = {"n": {}, "map": {}, "键": {}}

    def _占位(self, 场: dict, 类: str, 原: str, 归一: str = "") -> str:
        # 同一个号码带不带空格横杠，算同一个占位符
        键值 = (类, 归一 or 原)
        已 = 场.setdefault("键", {})
        if 键值 in 已:
            return 已[键值]
        场["n"][类] = 场["n"].get(类, 0) + 1
        键 = f"[{类}_{场['n'][类]}]"
        场["map"][键] = 原
        已[键值] = 键
        return 键

    # ---------- 脱敏 ----------
    @staticmethod
    def _只留数字(文: str) -> str:
        return re.sub(r"\D", "", 文)

    def _脱一段(self, 文: str, 场: dict) -> str:
        if not isinstance(文, str) or not 文:
            return 文
        v = self.valves

        def 换邮箱(m):
            return self._占位(场, "EMAIL", m.group(0))

        def 换身份证(m):
            段 = m.group(0)
            数 = re.sub(r"[^\dXx]", "", 段).upper()   # 末位 X 不能被当成非数字删掉
            if len(数) == 18 and self._身份证对(数):
                return self._占位(场, "ID", 段, 数)
            if len(数) == 15 and self._日期像样(数[8:12]):   # 15 位是 YYMMDD，月日取后四位
                return self._占位(场, "ID", 段, 数)
            return 段

        def 换卡(m):
            段 = m.group(0)
            数 = self._只留数字(段)
            if 16 <= len(数) <= 19 and self._银行卡对(数):
                return self._占位(场, "BANK", 段, 数)
            return 段

        def 换手机(m):
            段 = m.group(0)
            数 = self._只留数字(段)
            尾 = 数[-11:]                 # 去掉 +86
            if len(尾) == 11 and 尾[0] == "1":
                return self._占位(场, "PHONE", 段, 尾)
            return 段

        if v.mask_email:
            文 = self._邮箱.sub(换邮箱, 文)
        if v.mask_id:
            文 = self._身份证.sub(换身份证, 文)
            文 = self._身份证15.sub(换身份证, 文)
        if v.mask_bank:
            文 = self._银行卡.sub(换卡, 文)
        if v.mask_phone:
            文 = self._手机.sub(换手机, 文)
        if v.mask_uscc:
            文 = self._统一代码.sub(
                lambda m: self._占位(场, "USCC", m.group(0)) if self._统一代码对(m.group(0))
                else m.group(0), 文)
        if v.mask_tel:
            文 = self._固话.sub(lambda m: self._占位(场, "TEL", m.group(0)), 文)
            文 = self._客服电话.sub(lambda m: self._占位(场, "TEL", m.group(0)), 文)
        if v.mask_plate:
            文 = self._车牌.sub(lambda m: self._占位(场, "PLATE", m.group(0)), 文)
        if v.mask_passport:
            文 = self._护照.sub(lambda m: self._占位(场, "PASSPORT", m.group(0)), 文)
        return 文

    @staticmethod
    def _日期像样(月日: str) -> bool:
        try:
            月, 日 = int(月日[:2]), int(月日[2:])
        except ValueError:
            return False
        return 1 <= 月 <= 12 and 1 <= 日 <= 31

    def _还原一段(self, 文: str, 场: dict) -> str:
        if not isinstance(文, str) or not 文:
            return 文
        for k, v in 场["map"].items():
            if k in 文:
                文 = 文.replace(k, v)
        # 模型有时往方括号里塞空格（「[ PHONE_1 ]」），再兜一次
        def 换(m):
            键 = f"[{m.group(1)}_{m.group(2)}]"
            return 场["map"].get(键, m.group(0))
        文 = re.sub(r"\[\s*(PHONE|ID|BANK|EMAIL|TEL|PLATE|USCC|PASSPORT)\s*_\s*(\d+)\s*\]", 换, 文)
        return 文

    def _脱payload(self, body: dict, 场: dict) -> dict:
        for m in body.get("messages") or []:
            if "content" in m:
                if isinstance(m["content"], str):
                    m["content"] = self._脱一段(m["content"], 场)
                elif isinstance(m["content"], list):
                    for 段 in m["content"]:
                        if isinstance(段, dict) and isinstance(段.get("text"), str):
                            段["text"] = self._脱一段(段["text"], 场)
        return body

    def _日志路(self) -> Path:
        目录 = (self.valves.log_dir or "").strip()
        if 目录:
            return Path(目录) / "payload-log.jsonl"
        return Path(tempfile.gettempdir()) / "openwebui-pii-redact.jsonl"

    def _记一笔(self, 场键: str, body: dict) -> None:
        """落一行日志，只落脱敏后的样子——用来证明模型看到的是占位符。"""
        if not self.valves.log_payload:
            return
        try:
            最后 = ""
            for m in reversed(body.get("messages") or []):
                if m.get("role") == "user":
                    最后 = m.get("content") if isinstance(m.get("content"), str) else json.dumps(
                        m.get("content"), ensure_ascii=False)[:400]
                    break
            路 = self._日志路()
            路.parent.mkdir(parents=True, exist_ok=True)
            with 路.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                    "chat": 场键, "messages": len(body.get("messages") or []),
                                    "last_user": 最后[:400]}, ensure_ascii=False) + "\n")
        except Exception:
            pass

    # ---------- 钩子 ----------
    async def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        """一轮一次：清空这一场的计数和映射，然后把用户这句脱敏。"""
        键 = self._场键(body)
        self._上次场 = 键
        self._重置(键)
        场 = self._场(键)
        return self._脱payload(body, 场)

    async def request(self, body: dict, __user__: Optional[dict] = None) -> dict:
        """每次发给模型都过一遍（工具调用一轮会来好几次）。占位符不会再被匹配，所以可重复跑。"""
        键 = self._场键(body)
        self._上次场 = 键
        场 = self._场(键)
        体 = self._脱payload(body, 场)
        self._记一笔(键, 体)
        return 体

    async def outlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        if not self.valves.restore:
            return body
        场 = self._场(self._场键(body))
        for m in body.get("messages") or []:
            if m.get("role") == "assistant" and isinstance(m.get("content"), str):
                m["content"] = self._还原一段(m["content"], 场)
        if self.valves.log_payload:
            try:
                路 = self._日志路()
                路.parent.mkdir(parents=True, exist_ok=True)
                with 路.open("a", encoding="utf-8") as f:
                    # 只记条数，不记任何消息内容——日志里不许出现真号
                    f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": "outlet",
                                        "chat": self._场键(body),
                                        "map_n": len(场.get("map") or {})},
                                       ensure_ascii=False) + "\n")
            except Exception:
                pass
        return body

    def _上一个场(self) -> str:
        return getattr(self, "_上次场", "default")

    @staticmethod
    def _场键(body: dict) -> str:
        # 只认 chat_id；没有就归到默认场。
        # 不许退到 body["id"]——inlet 和 outlet 拿到的 id 不是同一个，会各存各的。
        meta = body.get("metadata") or {}
        return str(body.get("chat_id") or (meta.get("chat_id") if isinstance(meta, dict) else None) or "default")

    # ---------- 流式 ----------
    async def stream(self, event: dict, __user__: Optional[dict] = None) -> dict:
        """流式：SSE 每一块是 OpenAI 那种结构。占位符可能被拆开，尾巴先扣住。"""
        if not self.valves.restore:
            return event
        场 = self._场(self._场键(event) if event.get("chat_id") else self._上一个场())
        尾巴 = 场.get("tail", "")
        try:
            方向 = event.get("choices") or []
            for 项 in 方向:
                for 位置 in ("delta", "message"):
                    盒 = 项.get(位置) or {}
                    文 = 盒.get("content")
                    if not isinstance(文, str):
                        continue
                    合 = 尾巴 + 文
                    留 = 0
                    for i in range(min(12, len(合)), 0, -1):
                        尾 = 合[-i:]
                        if re.fullmatch(r"\[\s*[A-Z]*\s*(_\s*\d*)?\s*", 尾):
                            留 = i
                            break
                    能换 = 合[:len(合) - 留] if 留 else 合
                    场["tail"] = 合[len(合) - 留:] if 留 else ""
                    盒["content"] = self._还原一段(能换, 场)
                    if 留 == 0:
                        尾巴 = ""
        except Exception:
            pass
        return event
