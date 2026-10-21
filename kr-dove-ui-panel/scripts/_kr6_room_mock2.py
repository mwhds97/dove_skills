# -*- coding: utf-8 -*-
"""kr6_powers 局外选择面板 —— KR6 原版素材合成预览（v2）。

素材全部取自 KR6 本体（Genesis），**frame 名与 slice_rect 均照抄 KR6 自己的
kui_templates**，不猜：
  面板底    UI_settings_9slice_popup_bg_           ← group_options_big.lua
            slice(57.6, 84.35, 22.8, 226.75)
  局部底    room_tower_9slice_rooms_desktop_roster_bg_  ← group_power_roster_desktop.lua
            slice(20, 18.95, 40.15, 37.95)   （KR6 **法术名册**用的就是它）
  已带关卡底 room_tower_9slice_rooms_desktop_roster_bg_equipped_
  装饰带    room_tower_upgrade_9slice_band_          ← group_tower_upgrades_desktop.lua
  标题条    room_tower_upgrade_9slice_popup_title_bg_rooms_
  槽位框    room_tower_image_power_lvl_icon_frame_1_          （黄=未选）
            room_tower_image_power_lvl_bg_0003                （橙=选中）
            room_tower_image_power_lvl_frame_aqcuired_1_      （金=已获得）
  槽位阴影  room_tower_image_power_lvl_bg_shadow_

布局坐标与 kr6_powers_room.lua 改版后一致（原点 = 面板左上角）。
"""

import io
import os
import re
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

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
PLUGIN = os.path.join(PROJECT, "mods", "local", "kr6_powers", "_assets", "images")
FONTS = os.path.join(PROJECT, "KingdomRushDove", "_assets", "all-desktop", "fonts")

TMP = os.path.join(os.environ.get("TEMP", "."), "g9comp")
os.makedirs(TMP, exist_ok=True)

PANEL_W, PANEL_H = 920, 752
SCR_W, SCR_H = 1600, 1000

_idx = None


def index():
    global _idx
    if _idx is not None:
        return _idx
    d = {}
    for root in (GEN, PLUGIN):
        for f in os.listdir(root):
            if not f.endswith(".lua"):
                continue
            s = io.open(os.path.join(root, f), encoding="utf-8", errors="replace").read()
            for m in re.finditer(r"^\t([a-zA-Z0-9_]+)\s*=\s*\{", s, re.M):
                name = m.group(1)
                if name in d:
                    continue
                b = s[m.end():m.end() + 500]
                a = re.search(r'a_name\s*=\s*"([^"]+)"', b)
                q = re.search(r"f_quad\s*=\s*\{\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", b)
                sz = re.search(r"size\s*=\s*\{\s*(\d+)\s*,\s*(\d+)", b)
                if a and q and sz:
                    d[name] = (root, a.group(1), int(q.group(1)), int(q.group(2)),
                               int(q.group(3)), int(q.group(4)),
                               int(sz.group(1)), int(sz.group(2)))
    _idx = d
    return d


def sprite(frame):
    info = index().get(frame)
    if not info:
        print("  MISS  %s" % frame)
        return None
    root, dds, x, y, w, h, sw, sh = info
    dst = os.path.join(TMP, frame + ".png")
    if not os.path.exists(dst):
        r = subprocess.run([MAGICK, os.path.join(root, dds), "-crop",
                            "%dx%d+%d+%d" % (w, h, x, y), "+repage", dst],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print("  FAIL  %s" % frame)
            return None
    return Image.open(dst).convert("RGBA")


def g9(frame, sl, ow, oh):
    im = sprite(frame)
    if im is None:
        return None
    iw, ih = im.size
    L, T, W, H = sl
    tw1, tw2, tw3 = L, W, iw - (L + W)
    th1, th2, th3 = T, H, ih - (T + H)
    if tw2 <= 0 or th2 <= 0 or tw3 <= 0 or th3 <= 0:
        print("  BAD-SLICE %s sprite %dx%d slice=%s" % (frame, iw, ih, sl))
        return None
    cw = round((ow - tw1 - tw3) / tw2)
    ch = round((oh - th1 - th3) / th2)
    if cw < 1 or ch < 1:
        print("  NOFIT %s %dx%d cw=%d ch=%d" % (frame, iw, ih, cw, ch))
        return None
    sw = (ow - tw1 - tw3) / (cw * tw2)
    sh = (oh - th1 - th3) / (ch * th2)
    xs, ws = [0, int(L), int(L + W)], [tw1, tw2, tw3]
    ys, hs = [0, int(T), int(T + H)], [th1, th2, th3]
    colw = [ws[0] if i == 1 else ws[2] if i == cw + 2 else ws[1] * sw for i in range(1, cw + 3)]
    rowh = [hs[0] if j == 1 else hs[2] if j == ch + 2 else hs[1] * sh for j in range(1, ch + 3)]
    out = Image.new("RGBA", (ow, oh), (0, 0, 0, 0))
    xo = 0.0
    for i in range(1, cw + 3):
        ci = 0 if i == 1 else 2 if i == cw + 2 else 1
        yo = 0.0
        for j in range(1, ch + 3):
            cj = 0 if j == 1 else 2 if j == ch + 2 else 1
            box = (xs[ci], ys[cj], xs[ci] + ws[ci], ys[cj] + hs[cj])
            if box[2] > iw or box[3] > ih:
                continue
            pc = im.crop(box)
            dw, dh = max(1, round(colw[i - 1])), max(1, round(rowh[j - 1]))
            if pc.size != (dw, dh):
                pc = pc.resize((dw, dh), Image.LANCZOS)
            out.paste(pc, (round(xo), round(yo)), pc)
            yo += dh
        xo += max(1, round(colw[i - 1]))
    print("  OK    %-50s %dx%d -> %dx%d" % (frame, iw, ih, ow, oh))
    return out


def sc(frame, w, h):
    im = sprite(frame)
    if im is None:
        return None
    return im.resize((max(1, round(w)), max(1, round(h))), Image.LANCZOS)


def font(sz):
    for n in ("msyh.ttc", "msyhbd.ttc"):
        p = os.path.join(FONTS, n)
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, sz)
            except Exception:
                pass
    return ImageFont.load_default()


def main():
    print("=== 渲染 ===")
    # ⭐ 用插件自己生成的图集（_assets/images/kr6_room.lua）——与游戏里装的是同一套像素
    panel = g9("kr6_room_panel", (57.6, 84.35, 22.8, 226.75), PANEL_W, PANEL_H)
    roster = g9("kr6_room_roster", (20, 18.95, 40.15, 37.95), 664, 258)

    # ⚠⚠ **必须按 room.lua 的真实语义画**：`KView:draw` 用
    #   `ref_scale = ss.ref_scale * self.image_scale`，**无视 self.size**
    #   ⇒ 游戏里实际绘制尺寸 = 素材原生尺寸 × view.scale。
    #   所以这里也按 "原生 × scale" 复现，不能再按 target 尺寸画
    #   （否则预览"看着对"、游戏里框大一圈 —— 本次就是这么翻车的）。
    def fit(frame, target_w):
        im = sprite(frame)
        if im is None:
            return None
        s = target_w / im.width
        return im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))),
                         Image.LANCZOS)

    SLOT_FRAME_W = 124
    titlebar = fit("kr6_room_titlebar", 160)
    slot_def = fit("kr6_room_slot", SLOT_FRAME_W)
    slot_sel = fit("kr6_room_slot_sel", SLOT_FRAME_W)
    shadow = fit("kr6_room_slot_shadow", SLOT_FRAME_W)

    if not panel or not roster:
        print("关键素材缺失")
        return 1

    icons = {}
    for n in ("reinforcements", "aspect_of_sol", "rain_of_fire"):
        icons[n] = sc("in_game_icon_power_%s" % n, 74, 74)

    # ---- 屏幕底 ----
    scr = Image.new("RGBA", (SCR_W, SCR_H), (12, 9, 7, 255))
    bgi = sprite("kr6_rooms_bg_illustration")
    if bgi:
        r = max(SCR_W / bgi.width, SCR_H / bgi.height)
        b = bgi.resize((round(bgi.width * r), round(bgi.height * r)), Image.LANCZOS)
        scr.alpha_composite(b.crop((0, 0, SCR_W, SCR_H)))
        scr.alpha_composite(Image.new("RGBA", (SCR_W, SCR_H), (0, 0, 0, 120)))

    px, py = (SCR_W - PANEL_W) // 2, (SCR_H - PANEL_H) // 2
    scr.alpha_composite(panel, (px, py))

    lay = Image.new("RGBA", (PANEL_W, PANEL_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)

    # ---- 标题徽章（中心 y=52）----
    if titlebar:
        lay.alpha_composite(titlebar, (round((PANEL_W - titlebar.width) / 2),
                                       round(52 - titlebar.height / 2)))
    d.text((PANEL_W / 2, 52), "选择法术", font=font(18),
           fill=(255, 240, 210, 255), anchor="mm")

    # ---- 槽位小标题 ----
    d.text((PANEL_W / 2, 108), "已带入关卡", font=font(14),
           fill=(232, 216, 182, 255), anchor="mm")

    # ---- 槽位 ×3（与 room.lua 一致：SLOT 124 / GAP 36 / slots_y 120 / 框心 +62）----
    SLOT, GAP, SLOTS_Y, FRAME_CY = 124, 36, 120, 62
    total_w = 3 * SLOT + 2 * GAP
    sx0 = (PANEL_W - total_w) / 2
    names = ["援军", "索罗化身", "流星火雨"]
    keys = ("reinforcements", "aspect_of_sol", "rain_of_fire")
    for i in range(3):
        cx = sx0 + i * (SLOT + GAP) + SLOT / 2
        icy = SLOTS_Y + FRAME_CY
        fw = slot_sel if i == 1 else slot_def
        if fw:
            lay.alpha_composite(fw, (round(cx - fw.width / 2),
                                     round(icy - fw.height / 2)))
        if shadow:
            lay.alpha_composite(shadow, (round(cx - shadow.width / 2),
                                         round(SLOTS_Y + 114 - shadow.height / 2)))
        ic = icons.get(keys[i])
        if ic:
            lay.alpha_composite(ic, (round(cx - ic.width / 2),
                                     round(icy - ic.height / 2)))
        d.text((cx, SLOTS_Y + 140), names[i], font=font(13),
               fill=(255, 255, 255, 235), anchor="mm")
        d.text((cx, SLOTS_Y + 156), ["10s", "48s", "45s"][i], font=font(12),
               fill=(230, 214, 180, 220), anchor="mm")

    # ---- 列表小标题 ----
    LX, LW = (PANEL_W - 664) / 2, 664
    d.text((PANEL_W / 2, 302), "可用法术（点列表加入，点槽位取出）",
           font=font(13), fill=(232, 216, 182, 255), anchor="mm")

    # ---- 列表 ----
    LY = 312
    lay.alpha_composite(roster, (round(LX), LY))

    # ---- 列表行 ----
    order = ["aspect_of_sol", "rain_of_fire", "reinforcements"]
    cds = {"aspect_of_sol": "48s", "rain_of_fire": "45s", "reinforcements": "10s"}
    nm = {"aspect_of_sol": "索罗化身", "rain_of_fire": "流星火雨", "reinforcements": "援军"}
    for i, key in enumerate(order):
        ry = LY + 8 + i * 44
        if i < 2:
            d.rectangle([LX + 6, ry - 2, LX + 658, ry + 34],
                        fill=(96, 78, 40, 120))
        ic = icons.get(key)
        if ic:
            lay.alpha_composite(ic.resize((32, 32), Image.LANCZOS),
                                (round(LX + 14), ry))
        d.text((LX + 60, ry + 16), nm[key], font=font(15),
               fill=(255, 250, 235, 255), anchor="lm")
        d.text((LX + 500, ry + 16), cds[key], font=font(13),
               fill=(214, 208, 190, 255), anchor="lm")
        if i < 2:
            d.text((LX + 566, ry + 16), "已选", font=font(13),
                   fill=(150, 214, 130, 255), anchor="lm")

    # ---- 底部按钮（用框演示位置；中心 y=640 对齐 room.lua 的 by）----
    for label, bx in (("恢复默认", 360), ("取消", 560), ("确认", 760)):
        d.rounded_rectangle([bx - 66, 605, bx + 66, 676], radius=10,
                            fill=(58, 44, 28, 235), outline=(178, 142, 72, 255), width=2)
        color = (255, 240, 200, 255) if label == "确认" else (226, 210, 180, 255)
        d.text((bx, 640), label, font=font(17), fill=color, anchor="mm")

    scr.alpha_composite(lay, (px, py))
    out = os.path.abspath(sys.argv[1])
    scr.convert("RGB").save(out)
    print("\n合成预览: %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
