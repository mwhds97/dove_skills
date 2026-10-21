# -*- coding: utf-8 -*-
"""解析 Dove 的 KRAB 二进制图集索引（lib/klove/atlas_binary.lua 格式）。

为什么需要：Dove 本体的图集索引是 `.bin`（KRAB），**离线 love_stub 不加载**，
所以静态查帧名会得到假阴性（连本体自己在用的帧都查不到）。
本脚本按官方格式逐字节解析，用来做「帧名是否真的存在」的权威判定。

用法：
  python _krab_list.py <xxx.bin>              列出所有帧名
  python _krab_list.py <xxx.bin> <子串>        只列匹配子串的帧名

布局（小端）：
  "KRAB"  u8 version  u32 frame_count  u16 atlas_name_count [u16 len + bytes]*
  frame_count 条：u16 len+name, u16 atlas_idx, u16*4 f_quad, u16*2 a_size,
                  u16*2 trim12, f32 ref_scale, u16*2 size, u16 alias_count [u16 len+bytes]*
"""

import struct
import sys


def parse(path):
    with open(path, "rb") as f:
        b = f.read()

    if b[:4] != b"KRAB":
        raise SystemExit("不是 KRAB 格式（magic=%r）" % b[:4])

    p = 4
    ver = b[p]
    p += 1
    if ver != 1:
        raise SystemExit("版本 %d 未支持" % ver)

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

    frames = []
    for _ in range(frame_count):
        (ln,) = struct.unpack_from("<H", b, p)
        p += 2
        name = b[p:p + ln].decode("utf-8", "replace")
        p += ln

        a_idx, q1, q2, q3, q4, aw, ah, t1, t2 = struct.unpack_from("<9H", b, p)
        p += 18
        (ref_scale,) = struct.unpack_from("<f", b, p)
        p += 4
        s1, s2, alias_count = struct.unpack_from("<3H", b, p)
        p += 6

        aliases = []
        for _ in range(alias_count):
            (al,) = struct.unpack_from("<H", b, p)
            p += 2
            aliases.append(b[p:p + al].decode("utf-8", "replace"))
            p += al

        frames.append(dict(name=name, atlas=atlas_names[a_idx - 1] if a_idx - 1 < len(atlas_names) else "?",
                           quad=(q1, q2, q3, q4), a_size=(aw, ah), trim=(t1, t2),
                           ref_scale=ref_scale, size=(s1, s2), aliases=aliases))

    return atlas_names, frames


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    path = sys.argv[1]
    want = sys.argv[2] if len(sys.argv) > 2 else None

    names, frames = parse(path)
    print("图集名: %s" % names)
    print("帧数: %d（含 alias 展开）" % len(frames))
    expanded = 0
    for f in frames:
        expanded += len(f["aliases"])
    print("alias 目标数: %d" % expanded)
    print()

    hit = 0
    for f in frames:
        if want and want not in f["name"]:
            continue
        hit += 1
        print("%-46s atlas=%s quad=%s size=%s ref=%.4f"
              % (f["name"], f["atlas"], f["quad"], f["size"], f["ref_scale"]))
        for a in f["aliases"]:
            if not want or want in a:
                print("        alias -> %s" % a)
                hit += 1
    if want:
        print("\n匹配 %d 条" % hit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
