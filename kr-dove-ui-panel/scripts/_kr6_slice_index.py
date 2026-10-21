# -*- coding: utf-8 -*-
"""从 KR6 全部 kui_templates 里抓出 (image_name, size, slice_rect) 三元组。

为什么：GG9View 的 slice_rect 必须**照抄 KR6 自己的定义**，不能猜
（切错就会像第一次那样把面板切成上下两截的平板）。
本脚本建立「帧名 → KR6 实际使用的 slice_rect + 目标尺寸」索引，
供挑素材 / 生成预览用。
"""

import io
import os
import re
import sys
from collections import defaultdict

def _find_project():
    p = os.path.dirname(os.path.abspath(__file__))
    for _ in range(12):
        if os.path.isdir(os.path.join(p, "KingdomRushDove")):
            return p
        p = os.path.dirname(p)
    return os.environ.get("KR_DOVE_PROJECT", "")


PROJECT = _find_project()
if not PROJECT:
    raise SystemExit("找不到工程根（应含 KingdomRushDove 子目录）；请设 KR_DOVE_PROJECT")
WS = os.path.dirname(PROJECT)
KR6_ROOT = os.environ.get("KR6_SRC", os.path.join(WS, "Kingdom Rush Genesis"))
MAGICK = os.environ.get("MAGICK", r"D:\app\ImageMagick-7.1.2-Q16-HDRI\magick.exe")
TPL = os.path.join(KR6_ROOT, "Kingdom Rush Genesis", "kr6", "data", "kui_templates")

# 匹配一个 GG59View 块（宽松版：从 class 声明往后找 image_name/size/slice_rect）
BLOCK = re.compile(
    r'image_name\s*=\s*"([^"]+)"\s*,\s*class\s*=\s*"GG59View"'
    r'|class\s*=\s*"GG59View"\s*,\s*(?:image_name\s*=\s*"([^"]+)")?',
)


def parse(path):
    s = io.open(path, encoding="utf-8", errors="replace").read()
    out = []
    # 逐个 { ... } 一级块
    for m in re.finditer(r"\{([^{}]*?)\}", s, re.S):
        b = m.group(1)
        if "GG59View" not in b:
            continue
        img = re.search(r'image_name\s*=\s*"([^"]+)"', b)
        sz = re.search(r"\bsize\s*=\s*v\(\s*([\d.]+)\s*,\s*([\d.]+)\s*\)", b)
        sl = re.search(r"slice_rect\s*=\s*r\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,"
                       r"\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)", b)
        if img and sl:
            out.append((img.group(1),
                        (float(sz.group(1)), float(sz.group(2))) if sz else None,
                        tuple(float(x) for x in sl.groups()),
                        os.path.basename(path)))
    return out


def main():
    idx = defaultdict(list)
    for f in sorted(os.listdir(TPL)):
        if not f.endswith(".lua"):
            continue
        for img, sz, sl, src in parse(os.path.join(TPL, f)):
            idx[img].append((sz, sl, src))

    print("=== 帧名 → (size, slice_rect, 出处) 共 %d 个 GG59View 引用 ===" % len(idx))
    for img in sorted(idx):
        for sz, sl, src in idx[img]:
            print("%-58s size=%-20s slice=%-30s %s"
                  % (img, str(sz), str(sl), src))
    return 0


if __name__ == "__main__":
    sys.exit(main())
