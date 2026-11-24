# -*- coding: utf-8 -*-
"""三组测试都可直接跑：没装 pydantic 也不用管，_stub 会顶上。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _stub

_stub.装好()
