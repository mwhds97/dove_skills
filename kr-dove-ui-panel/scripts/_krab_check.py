# -*- coding: utf-8 -*-
"""在 Dove 本体全部 KRAB 图集里查帧名是否存在 —— 「帧名是否真的存在」的权威判定。

为什么需要（踩过两次）：
  · 离线 love_stub **不加载 KRAB 二进制索引** ⇒ 静态 grep 全是假阴性
    （连本体自己在用的帧都查不到）
  · KR6 与 Dove 的同名字段**常常不同前缀**（如头像：KR6 `gui_bottom_info_image_soldiers_0068`
    vs Dove `kr6_info_portraits_soldiers_0068`）⇒ 抄 KR6 名就崩
    `kui.lua:529 attempt to index local 'ss'` + `image_db.error Sprite X was not found`

用法：
  python _krab_check.py                    # 建索引并打印统计
  python _krab_check.py <名1> <名2> ...     # 逐个报告命中/未命中
  python _krab_check.py --list <子串>       # 列出含该子串的所有帧

索引缓存：.workbuddy/_krab_index.json（首次较慢，之后秒回）
"""

import glob
import json
import os
import struct
import sys

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
DOVE = os.path.join(PROJECT, "KingdomRushDove", "_assets")
CACHE = os.environ.get("KRAB_INDEX", os.path.join(PROJECT, ".workbuddy", "_krab_index.json"))
PLUGIN_IMAGES = os.path.join(PROJECT, "mods", "local", "kr6_powers", "_assets", "images")


def parse_krab(path):
    with open(path, "rb") as f:
        b = f.read()
    if b[:4] != b"KRAB":
        return None
    p = 5  # magic + version
    (frame_count,) = struct.unpack_from("<I", b, p)
    p += 4
    (name_count,) = struct.unpack_from("<H", b, p)
    p += 2
    atlas_names = []
    for _ in range(name_count):
        (ln,) = struct.unpack_from("<H", b, p)
        p += 2
        atlas_names.append(b[p:p + ln].decode("utf-8", "replace"))
        p += ln

    out = {}
    for _ in range(frame_count):
        (ln,) = struct.unpack_from("<H", b, p)
        p += 2
        name = b[p:p + ln].decode("utf-8", "replace")
        p += ln
        a_idx = struct.unpack_from("<H", b, p)[0]
        p += 18 + 4  # 9H(f_quad4+a_size2+trim2+idx1) 已读 idx；余 8H=16 + f32=4
        s1, s2, alias_count = struct.unpack_from("<3H", b, p)
        p += 6
        aname = atlas_names[a_idx - 1] if 0 <= a_idx - 1 < len(atlas_names) else "?"
        out[name] = aname
        for _ in range(alias_count):
            (al,) = struct.unpack_from("<H", b, p)
            p += 2
            out[b[p:p + al].decode("utf-8", "replace")] = aname
            p += al
    return out


def parse_lua_atlas(path):
    """插件自己的图集索引（return { frame = { ... } } 文本 lua）。"""
    out = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            t = line.strip()
            if t.endswith("= {") and t[0].isalpha():
                out[t[:-3].strip()] = os.path.basename(path)
            elif t.startswith('"') and t.endswith('",'):
                out[t[1:-2]] = os.path.basename(path)   # alias 目标
    return out


def build(force=False):
    if os.path.exists(CACHE) and not force:
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)

    idx = {}
    n_bin = 0
    for p in glob.glob(os.path.join(DOVE, "**", "*.bin"), recursive=True):
        try:
            d = parse_krab(p)
        except Exception:
            continue
        if d:
            n_bin += 1
            for k, v in d.items():
                idx.setdefault(k, v)
    for p in glob.glob(os.path.join(PLUGIN_IMAGES, "*.lua")):
        for k, v in parse_lua_atlas(p).items():
            idx.setdefault(k, v)

    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(idx, f)
    print("索引建立：%d 个 bin + 插件图集 ⇒ %d 个帧名" % (n_bin, len(idx)))
    return idx


def main():
    args = sys.argv[1:]
    force = "--rebuild" in args
    args = [a for a in args if a != "--rebuild"]
    idx = build(force)

    if not args:
        print("帧名总数: %d" % len(idx))
        print("缓存: %s" % CACHE)
        return 0

    if args[0] == "--list":
        sub = args[1] if len(args) > 1 else ""
        hit = sorted(k for k in idx if sub in k)
        for k in hit:
            print("%-52s %s" % (k, idx[k]))
        print("\n匹配 %d 条" % len(hit))
        return 0

    miss = [a for a in args if a not in idx]
    for a in args:
        print("%-52s %s" % (a, idx.get(a, "<<< 不存在")))
    print("\n%d/%d 存在；缺失 %d" % (len(args) - len(miss), len(args), len(miss)))
    return 1 if miss else 0


if __name__ == "__main__":
    sys.exit(main())
