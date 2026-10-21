# -*- coding: utf-8 -*-
"""KR6 面板素材候选：按 Dove 的 GG9View 算法离线渲染预览（纯 PIL，不用 magick 拼命令行）。

GG9View 算法（严格照抄 all/gg_views.lua:661-745，ref_scale=1）：
    p1x,p2x = L, L+W ; p1y,p2y = T, T+H
    tw1,tw2,tw3 = L, W, imgw-(L+W)
    th1,th2,th3 = T, H, imgh-(T+H)
    cw = round((out_w-tw1-tw3)/tw2) ; sw = (out_w-tw1-tw3)/(cw*tw2)
    ch = round((out_h-th1-th3)/th2) ; sh = (out_h-th1-th3)/(ch*th2)
    中间格**平铺并缩放** sw/sh；边缘行列保持原尺寸。

输出：把多个候选渲染到同一尺寸后拼成一张对比图。
"""

import io
import json
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
ATLAS = os.path.join(KR6_ROOT, "Kingdom Rush Genesis", "_assets", "kr6-desktop",
                     "images", "fullhd_bc3")
TMP = os.path.join(os.environ.get("TEMP", "."), "g9pil")
os.makedirs(TMP, exist_ok=True)

# 预算好的索引：帧名 -> (lua, dds, x, y, w, h, sw, sh)
_INDEX = None


def build_index():
    global _INDEX
    if _INDEX is not None:
        return _INDEX
    idx = {}
    for f in os.listdir(ATLAS):
        if not f.endswith(".lua"):
            continue
        s = io.open(os.path.join(ATLAS, f), encoding="utf-8", errors="replace").read()
        for m in re.finditer(r"^\t([a-zA-Z0-9_]+)\s*=\s*\{", s, re.M):
            name = m.group(1)
            b = s[m.end():m.end() + 500]
            dds = re.search(r'a_name\s*=\s*"([^"]+)"', b)
            q = re.search(r"f_quad\s*=\s*\{\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", b)
            sz = re.search(r"size\s*=\s*\{\s*(\d+)\s*,\s*(\d+)", b)
            if dds and q and sz and name not in idx:
                idx[name] = (f, dds.group(1), int(q.group(1)), int(q.group(2)),
                             int(q.group(3)), int(q.group(4)),
                             int(sz.group(1)), int(sz.group(2)))
    _INDEX = idx
    return idx


def sprite_png(frame):
    idx = build_index()
    info = idx.get(frame)
    if not info:
        return None, None
    lua, dds, x, y, w, h, sw, sh = info
    dst = os.path.join(TMP, frame + ".png")
    if not os.path.exists(dst):
        r = subprocess.run([MAGICK, "dds:" + os.path.join(ATLAS, dds),
                            "-crop", "%dx%d+%d+%d" % (w, h, x, y), "+repage", dst],
                           capture_output=True, text=True)
        if r.returncode != 0:
            return None, None
    return dst, info


def render_9slice(frame, sl, out_w, out_h):
    png, info = sprite_png(frame)
    if not png:
        return None, "帧不存在"
    im = Image.open(png).convert("RGBA")
    iw, ih = im.size
    L, T, W, H = sl
    tw1, tw2, tw3 = L, W, iw - (L + W)
    th1, th2, th3 = T, H, ih - (T + H)
    if tw2 <= 0 or th2 <= 0 or tw3 <= 0 or th3 <= 0:
        return None, "slice 超出素材 %dx%d" % (iw, ih)
    cw = round((out_w - tw1 - tw3) / tw2)
    ch = round((out_h - th1 - th3) / th2)
    if cw < 1 or ch < 1:
        return None, "尺寸不足 cw=%d ch=%d (素材 %dx%d)" % (cw, ch, iw, ih)
    sw = (out_w - tw1 - tw3) / (cw * tw2)
    sh = (out_h - th1 - th3) / (ch * th2)

    xs, ws = [0, int(L), int(L + W)], [tw1, tw2, tw3]
    ys, hs = [0, int(T), int(T + H)], [th1, th2, th3]
    colw = [ws[0] if i == 1 else ws[2] if i == cw + 2 else ws[1] * sw
            for i in range(1, cw + 3)]
    rowh = [hs[0] if j == 1 else hs[2] if j == ch + 2 else hs[1] * sh
            for j in range(1, ch + 3)]

    out = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
    xoff = 0.0
    for i in range(1, cw + 3):
        ci = 0 if i == 1 else 2 if i == cw + 2 else 1
        yoff = 0.0
        for j in range(1, ch + 3):
            cj = 0 if j == 1 else 2 if j == ch + 2 else 1
            box = (xs[ci], ys[cj], xs[ci] + ws[ci], ys[cj] + hs[cj])
            if box[2] > iw or box[3] > ih or box[0] < 0 or box[1] < 0:
                continue
            piece = im.crop(box)
            dw, dh = max(1, round(colw[i - 1])), max(1, round(rowh[j - 1]))
            if piece.size != (dw, dh):
                piece = piece.resize((dw, dh), Image.NEAREST)
            out.paste(piece, (round(xoff), round(yoff)), piece)
            yoff += dh
        xoff += max(1, round(colw[i - 1]))
    return out, "cw=%d ch=%d sw=%.2f sh=%.2f" % (cw, ch, sw, sh)


def main():
    spec = json.load(open(sys.argv[1], encoding="utf-8"))
    out_path = os.path.abspath(sys.argv[2])
    tiles = []
    for it in spec:
        res, note = render_9slice(it["frame"], it["slice"],
                                  it["out"][0], it["out"][1])
        sp = build_index().get(it["frame"])
        sz = "%dx%d" % (sp[5], sp[6]) if sp else "?"
        if res is None:
            print("  FAIL  %-52s sprite %-10s %s" % (it["frame"], sz, note))
            continue
        print("  OK    %-52s sprite %-10s %s" % (it["frame"], sz, note))
        bg = Image.new("RGBA", res.size, (20, 16, 12, 255))
        bg.alpha_composite(res)
        tiles.append((it["frame"], bg))

    if not tiles:
        print("无成功渲染项")
        return 1

    ow, oh = tiles[0][1].size
    pad, lab = 14, 22
    cols = 3
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB",
                      (cols * (ow + pad) + pad, rows * (oh + lab + pad) + pad),
                      (18, 14, 10))
    for k, (name, im) in enumerate(tiles):
        r, c = divmod(k, cols)
        sheet.paste(im.convert("RGB"), (pad + c * (ow + pad),
                                       pad + r * (oh + lab + pad)))
    sheet.save(out_path)
    print("\n对比图: %s  (%d 个候选，%dx%d/格)" % (out_path, len(tiles), ow, oh))
    return 0


if __name__ == "__main__":
    sys.exit(main())
