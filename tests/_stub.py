# -*- coding: utf-8 -*-
"""测试用的小垫片：没装 pydantic 也能跑。

插件在 Open WebUI 里跑，那边一定有 pydantic；但别人在自己电脑上验，未必装了。
这里给一个极简替身，只满足 filter.py 用到的「带默认值的字段类」。
"""
import sys


def 装好():
    try:
        import pydantic  # noqa: F401
        return
    except Exception:
        pass

    class BaseModel:
        def __init__(self, **kw):
            类 = type(self)
            for 名 in dir(类):
                if 名.startswith("_"):
                    continue
                值 = getattr(类, 名)
                if isinstance(值, (bool, int, str, float)) or 值 is None:
                    setattr(self, 名, kw.get(名, 值))

    class _虚:
        pass

    _虚.BaseModel = BaseModel
    sys.modules["pydantic"] = _虚
