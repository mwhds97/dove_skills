# -*- coding: utf-8 -*-
"""生成 kr6_powers 的局外面板图集 `kr6_room`（PNG + KRAB 风格 lua 索引）。

素材全部从 KR6 本体（Genesis fullhd_bc3）抽取，帧名统一加 `kr6_room_` 前缀
（图集键空间是全局的 `db_atlas` ⇒ 必须防撞本体）。

⚠ 关键约定（对齐 GG9View 的取数方式，all/gg_views.lua:661-745）：
  · `trim` 全 0、`size` == `f_quad` 宽高 ⇒ 逻辑坐标 == 素材像素坐标
  · 图集以 ref_scale=1 加载（同 kr6_power_ui）⇒ KR6 的 slice_rect 原值可直接用
"""

import io
import os
import re
import subprocess
import sys

from PIL import Image

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
GEN = os.path.join(KR6_ROOT, "Kingdom Rush Genesis", "_assets", "kr6-desktop",
                   "images", "fullhd_bc3")
DST = os.path.join(PROJECT, "mods", "local", "kr6_powers", "_assets", "images")
ATLAS = "kr6_room"

# 新帧名 -> KR6 源帧名
FRAMES = [
    ("kr6_room_panel", "UI_settings_9slice_popup_bg_"),
    ("kr6_room_roster", "room_tower_9slice_rooms_desktop_roster_bg_"),
    ("kr6_room_titlebar", "room_tower_upgrade_9slice_popup_title_bg_rooms_"),
    ("kr6_room_slot", "room_tower_image_power_lvl_bg_0001"),
    ("kr6_room_slot_sel", "room_tower_image_power_lvl_bg_0003"),
    ("kr6_room_slot_acq", "room_tower_image_power_lvl_frame_aqcuired_1_"),
    ("kr6_room_slot_shadow", "room_tower_image_power_lvl_bg_shadow_"),
]

_idx = None


def genesis_index():
    global _idx
    if _idx is not None:
        return _idx
    d = {}
    for f in os.listdir(GEN):
        if not f.endswith(".lua"):
            continue
        s = io.open(os.path.join(GEN, f), encoding="utf-8", errors="replace").read()
        # ⚠ 字符类里**不能含空格**：`[a-zA-Z0-9_ ]+` 会把 `= ` 前的尾随空格
        #   一起贪婪吃进捕获组 ⇒ 键名带尾空格 ⇒ 查不到（本次踩过）。
        for m in re.finditer(r"^\t([a-zA-Z0-9_]+)\s*=\s*\{", s, re.M):
            name = m.group(1)
            if name in d:
                continue
            b = s[m.end():m.end() + 500]
            a = re.search(r'a_name\s*=\s*"([^"]+)"', b)
            q = re.search(r"f_quad\s*=\s*\{\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", b)
            if a and q:
                d[name] = (a.group(1), int(q.group(1)), int(q.group(2)),
                           int(q.group(3)), int(q.group(4)))
    _idx = d
    return d


def extract(src_frame, tmp_png):
    info = genesis_index().get(src_frame)
    if not info:
        print("  MISS  %s" % src_frame)
        return None
    dds, x, y, w, h = info
    r = subprocess.run([MAGICK, "dds:" + os.path.join(GEN, dds),
                        "-crop", "%dx%d+%d+%d" % (w, h, x, y), "+repage", tmp_png],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("  FAIL  %s" % src_frame)
        return None
    return Image.open(tmp_png).convert("RGBA")


def main():
    tmp = os.path.join(os.environ.get("TEMP", "."), "kr6room")
    os.makedirs(tmp, exist_ok=True)
    os.makedirs(DST, exist_ok=True)

    print("=== 抽取 KR6 素材 ===")
    got = []
    for new_name, src in FRAMES:
        im = extract(src, os.path.join(tmp, new_name + ".png"))
        if im is None:
            continue
        got.append((new_name, src, im))
        print("  OK    %-24s ← %-50s %dx%d" % (new_name, src, im.width, im.height))

    if not got:
        print("没有抽到任何素材")
        return 1

    # ---- 紧凑排布（简单行式，左到右，超宽换行）----
    MAXW = 2048
    PAD = 1
    x = y = 0
    row_h = 0
    placed = []
    for name, src, im in got:
        if x + im.width + PAD > MAXW and x > 0:
            x = 0
            y += row_h + PAD
            row_h = 0
        placed.append((name, src, im, x, y))
        x += im.width + PAD
        row_h = max(row_h, im.height)
    atlas_w = MAXW
    atlas_h = y + row_h

    sheet = Image.new("RGBA", (atlas_w, atlas_h), (0, 0, 0, 0))
    for name, src, im, px, py in placed:
        sheet.paste(im, (px, py))

    png_name = ATLAS + "-1.png"
    sheet.save(os.path.join(DST, png_name))
    print("\n=== 图集 ===")
    print("  %s  %dx%d" % (png_name, atlas_w, atlas_h))

    # ---- 写 lua 索引（KRAB 风格；与 kr6_power_ui.lua 同格式）----
    lines = [
        "-- KR6 原版局外面板素材（Genesis fullhd_bc3 抽取）",
        "-- 帧名加 kr6_room_ 前缀：图集键空间是全局 db_atlas，必须防撞本体。",
        "-- ⭐ trim 全 0 / size == f_quad ⇒ 逻辑坐标 == 素材像素，配 GG9View 时",
        "--   slice_rect 可直接用 KR6 kui_templates 里的原值（ref_scale=1 加载）。",
        "-- 生成脚本：.workbuddy/_gen_kr6_room_atlas.py（勿手改本文件）",
        "",
        "return {",
    ]
    for name, src, im, px, py in placed:
        lines += [
            "\t%s = {" % name,
            '\t\ta_name = "%s",' % png_name,
            "\t\tsize = {",
            "\t\t\t%d," % im.width,
            "\t\t\t%d" % im.height,
            "\t\t},",
            "\t\ttrim = {",
            "\t\t\t0,",
            "\t\t\t0,",
            "\t\t\t0,",
            "\t\t\t0",
            "\t\t},",
            "\t\ta_size = {",
            "\t\t\t%d," % atlas_w,
            "\t\t\t%d" % atlas_h,
            "\t\t},",
            "\t\tf_quad = {",
            "\t\t\t%d," % px,
            "\t\t\t%d," % py,
            "\t\t\t%d," % im.width,
            "\t\t\t%d" % im.height,
            "\t\t},",
            "\t\talias = {}",
            "\t},",
        ]
    lines += ["}", ""]

    lua_path = os.path.join(DST, ATLAS + ".lua")
    io.open(lua_path, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
    print("  %s.lua  %d 帧" % (ATLAS, len(placed)))
    print("\n完成：%s" % DST)
    return 0


if __name__ == "__main__":
    sys.exit(main())
