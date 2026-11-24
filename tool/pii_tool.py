# -*- coding: utf-8 -*-
"""命令行脱敏工具：同一个规则，处理文件而不是聊天。

用法（在仓库根目录）：

    python tool/pii_tool.py preview  sample.txt        # 只看会改哪几处，不动文件
    python tool/pii_tool.py redact   sample.txt        # 生成 sample.redacted.txt + sample.map.json
    python tool/pii_tool.py restore  sample.redacted.txt --map sample.map.json

支持 .txt / .md / .csv（逐格处理，不动分隔符）/ .xlsx（逐格处理，需要 openpyxl）。
映射表里是真值，别外传——用完就删。
"""
import argparse
import csv
import importlib.util
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

根 = Path(__file__).resolve().parent.parent


def 装插件模块():
    """直接复用插件那份规则，不做第二套。插件依赖 pydantic，没装就给个替身。"""
    try:
        import pydantic  # noqa: F401
    except Exception:
        替 = type(sys)("pydantic")

        class BaseModel:
            def __init__(self, **kw):
                类 = type(self)
                for 名 in dir(类):
                    if 名.startswith("_"):
                        continue
                    值 = getattr(类, 名)
                    if isinstance(值, (bool, int, str, float)) or 值 is None:
                        setattr(self, 名, kw.get(名, 值))

        替.BaseModel = BaseModel
        sys.modules["pydantic"] = 替

    spec = importlib.util.spec_from_file_location("pii_filter", 根 / "filter.py")
    模 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(模)
    return 模


def 读格(路: Path):
    """返回 (数据, 模式, 写回函数)。模式：'格' 是表格，'行' 是纯文本。"""
    后 = 路.suffix.lower()
    if 后 == ".csv":
        with 路.open(encoding="utf-8-sig", newline="") as f:
            行 = [r for r in csv.reader(f)]
        def 写(新行, 出: Path):
            with 出.open("w", encoding="utf-8-sig", newline="") as f:
                csv.writer(f).writerows(新行)
        return 行, "格", 写

    if 后 in (".xlsx", ".xlsm"):
        try:
            import openpyxl
        except Exception:
            print("处理 xlsx 需要 openpyxl：pip install openpyxl", file=sys.stderr)
            raise SystemExit(2)
        书 = openpyxl.load_workbook(路)
        行 = [[(c.value if isinstance(c.value, str) else c.value) for c in r] for r in 书.active.iter_rows()]
        def 写(新行, 出: Path):
            新 = openpyxl.Workbook()
            新页 = 新.active
            for r in 新行:
                新页.append(r)
            新.save(出)
        return 行, "格", 写

    return (路.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True),
            "行",
            lambda 新行, 出: 出.write_text("".join(新行), encoding="utf-8"))


def 主():
    解 = argparse.ArgumentParser(description="中文敏感信息脱敏（命令行版）")
    解.add_argument("动作", choices=["preview", "redact", "restore"])
    解.add_argument("文件")
    解.add_argument("--out", default="")
    解.add_argument("--map", dest="映射", default="")
    参 = 解.parse_args()

    源 = Path(参.文件)
    if not 源.is_file():
        print("找不到文件：", 源, file=sys.stderr)
        raise SystemExit(2)

    模 = 装插件模块()

    if 参.动作 == "restore":
        if not 参.映射:
            print("还原需要 --map 指向映射表", file=sys.stderr)
            raise SystemExit(2)
        映射 = json.loads(Path(参.映射).read_text(encoding="utf-8"))
        反 = {k: v for k, v in 映射.items()}

        def 换(文):
            for k, v in 反.items():
                文 = 文.replace(k, v)
            return 文

        行, 模式, 写回 = 读格(源)
        if 模式 == "格":
            新行 = [[换(c) if isinstance(c, str) else c for c in r] for r in 行]
        else:
            新行 = [换(l) for l in 行]
        出 = Path(参.out) if 参.out else 源.with_name(源.stem + ".restored" + 源.suffix)
        写回(新行, 出)
        print("还原完成 →", 出)
        return

    f = 模.Filter()
    场 = {"n": {}, "map": {}, "键": {}}

    def 换(文):
        return f._脱一段(文, 场)

    行, 模式, 写回 = 读格(源)
    if 模式 == "格":
        新行 = [[换(c) if isinstance(c, str) else c for c in r] for r in 行]
    else:
        新行 = [换(l) for l in 行]

    映射 = 场["map"]
    记数 = {}
    for k in 映射:
        类 = k.strip("[]").rsplit("_", 1)[0]
        记数[类] = 记数.get(类, 0) + 1

    print(f"这{'张表' if 模式 == '格' else '个文件'}里换掉 {len(映射)} 处：")
    for 类, n in sorted(记数.items()):
        print(f"  {类:<9} {n:>3} 处")

    if 参.动作 == "preview":
        示例 = list(映射.items())[:5]
        if 示例:
            print("\n前几处长这样（左＝原文，右＝发出去的样子）：")
            for k, v in 示例:
                print(f"  {v[:28]:<30} → {k}")
        print("\n（只是预览，没写任何文件）")
        return

    出 = Path(参.out) if 参.out else 源.with_name(源.stem + ".redacted" + 源.suffix)
    写回(新行, 出)
    映射路 = Path(参.映射) if 参.映射 else 源.with_name(源.stem + ".map.json")
    映射路.write_text(json.dumps(映射, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n脱敏版 →", 出)
    print("映射表 →", 映射路)
    print("映射表里是真值，用完请删掉。")


if __name__ == "__main__":
    主()
