# -*- coding: utf-8 -*-
"""kr6_powers 局外选择面板（KR6 原版素材版）：布局几何自检 + 示意图。

为什么要有这个：面板改版只能靠用户截图反馈，一轮来回很贵。
先把 room.lua 里的**显式坐标常量**复刻到这里，算出每个元素的矩形，
① 检查出界 ② 检查主要块重叠 ③ 检查槽位内元素是否越界 ④ 画示意图。

⚠ 数据是**手抄** room.lua 的常量，改布局必须同步改这里。
"""

import os

from PIL import Image, ImageDraw, ImageFont

W, H = 920, 752

# 标题徽章（kr6_room_titlebar 原生 306x177，按 scale 缩到 160 宽）
TITLE_W = 160
TITLE_H = 177 * (160 / 306)
TITLE_CY = 52
# 槽位区
SLOT, SLOT_H, GAP, SLOTS_Y = 124, 172, 36, 120
CAP_Y = 100
TOTAL_W = 3 * SLOT + 2 * GAP        # 444
SX = (W - TOTAL_W) / 2              # 238
# 槽位内（相对槽位左上角）
# 框：原生 157x155 缩到 124 宽 => 124 x 122.4（用 scale 缩放，见 room.lua）
FRAME_W = 124
FRAME_H = 155 * (124 / 157)
FRAME_CY = 62      # 框（中心对齐图标）
ICON = 108 * 0.68                               # 73.44
SHADOW_W = 124
SHADOW_H = 39 * (124 / 158)
SHADOW_CY = 114
SLOT_NAME_Y, SLOT_CD_Y = 132, 148
# 列表
LIST_W, LIST_H, LIST_Y = 664, 258, 312
LX = (W - LIST_W) / 2               # 128
POOL_CAP_Y = 292
HINT_Y = 574
# 按钮
BTN_W, BTN_H = 143, 71
BTN_Y = 640
BTN_XS = (360, 560, 760)

elems = []          # (layer, name, x, y, w, h)


def add(layer, name, x, y, w, h):
    elems.append((layer, name, x, y, w, h))


def cxy(cx, cy, w, h):
    return cx - w / 2, cy - h / 2, w, h


add("main", "标题条", *cxy(W / 2, TITLE_CY, TITLE_W, TITLE_H))
add("main", "标题文字", (W - 200) / 2, TITLE_CY - 15, 200, 30)
add("main", "槽位小标题", SX, CAP_Y, TOTAL_W, 16)
for i in range(3):
    sx = SX + i * (SLOT + GAP)
    add("main", "槽位%d" % (i + 1), sx, SLOTS_Y, SLOT, SLOT_H)
    add("slot", "槽位框", *cxy(sx + SLOT / 2, SLOTS_Y + FRAME_CY, FRAME_W, FRAME_H))
    add("slot", "图标", *cxy(sx + SLOT / 2, SLOTS_Y + FRAME_CY, ICON, ICON))
    add("slot", "阴影", *cxy(sx + SLOT / 2, SLOTS_Y + SHADOW_CY, SHADOW_W, SHADOW_H))
    add("slot", "名字", sx, SLOTS_Y + SLOT_NAME_Y, SLOT, 16)
    add("slot", "冷却", sx, SLOTS_Y + SLOT_CD_Y, SLOT, 16)
add("main", "列表小标题", LX, POOL_CAP_Y, LIST_W, 20)
add("main", "列表底/列表", LX, LIST_Y, LIST_W, LIST_H)
add("main", "提示", LX, HINT_Y, LIST_W, 22)
for nm, bx in zip(("恢复默认", "取消", "确认"), BTN_XS):
    add("main", nm, *cxy(bx, BTN_Y, BTN_W, BTN_H))

ROW_H = 44
rows = []
for i in range(3):
    ry = LIST_Y + i * ROW_H
    rows.append(("行%d" % (i + 1), LX, ry, LIST_W, ROW_H))
    rows.append(("  行图标", LX + 8, ry + 5, 108 * 0.34, 108 * 0.34))
    rows.append(("  行名字", LX + 56, ry + 8, 380, 28))
    rows.append(("  行冷却", LX + 446, ry + 8, 90, 28))
    rows.append(("  行已选", LX + 540, ry + 8, 110, 28))

# ---------------- 检查 ----------------
print("面板 %dx%d  （槽位 %dx%d ×3，间距 %d）" % (W, H, SLOT, SLOT_H, GAP))

print("\n=== ① 出界检查 ===")
bad = 0
for layer, n, x, y, w, h in elems:
    if x < -0.01 or y < -0.01 or x + w > W + 0.01 or y + h > H + 0.01:
        print("  OUT  %-10s (%.1f,%.1f)-(%.1f,%.1f)" % (n, x, y, x + w, y + h))
        bad += 1
print("  全部在图内 ✓" if bad == 0 else "  %d 项出界 ✗" % bad)

print("\n=== ② 主要块重叠检查 ===")


def overlap(a, b):
    _, _, ax, ay, aw, ah = a
    _, _, bx, by, bw, bh = b
    return not (ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay)


DECOR = {"标题条", "槽位小标题", "列表小标题", "标题文字"}
main = [e for e in elems if e[0] == "main" and e[1] not in DECOR]
ov = 0
for i in range(len(main)):
    for j in range(i + 1, len(main)):
        if overlap(main[i], main[j]):
            print("  OVERLAP  %s × %s" % (main[i][1], main[j][1]))
            ov += 1
print("  主要块无重叠 ✓" if ov == 0 else "  %d 处重叠 ✗" % ov)

print("\n=== ③ 槽位内元素是否落在槽位范围内 ===")
bad3 = 0
for i in range(3):
    sx = SX + i * (SLOT + GAP)
    for layer, n, ex, ey, ew, eh in elems:
        if layer != "slot":
            continue
        # 用 x 归属判断属于哪个槽位
        if not (sx - 1 <= ex <= sx + SLOT + 1):
            continue
        inside = ex >= sx - 0.01 and ex + ew <= sx + SLOT + 0.01 \
            and ey >= SLOTS_Y - 0.01 and ey + eh <= SLOTS_Y + SLOT_H + 0.01
        if not inside:
            print("  OUT  槽位%d %s (%.1f,%.1f)-(%.1f,%.1f) 超出容器 (%.0f,%.0f)-(%.0f,%.0f)"
                  % (i + 1, n, ex, ey, ex + ew, ey + eh,
                     sx, SLOTS_Y, sx + SLOT, SLOTS_Y + SLOT_H))
            bad3 += 1
print("  槽位内元素全部在容器内 ✓" if bad3 == 0 else "  %d 项越界 ✗" % bad3)

print("\n=== ④ 槽位内纵向排布（仅取第 1 个槽位）===")
sx1 = SX
# ⚠ "阴影"压框底是**设计意图**（框的厚度感）⇒ 排除出重叠检查，只查内容层
CONTENT = ("名字", "冷却")
sl = sorted([e for e in elems if e[0] == "slot" and e[1] in CONTENT
             and abs(e[2] - sx1) < 1.5], key=lambda e: e[3])
for layer, n, x, y, w, h in sl:
    print("  %-8s y %.0f -> %.0f" % (n, y, y + h))
ok = all(sl[k][3] + sl[k][5] <= sl[k + 1][3] + 0.01 for k in range(len(sl) - 1))
print("  无重叠 OK" if ok else "  有重叠 FAIL")

print("\n=== ⑤ 列表行 ===")
for nq, x, y, w, h in rows:
    if y + h > LIST_Y + LIST_H + 0.01 or x + w > LX + LIST_W + 0.01:
        print("  行溢出: %s (%.1f,%.1f)-(%.1f,%.1f)" % (nq, x, y, x + w, y + h))
print("  行内容均在列表内（或空）")

print("\n=== ⑥ 底边留白 ===")
print("  按钮底 %.0f → 面板底 %d，余 %d" % (BTN_Y + BTN_H / 2, H, H - BTN_Y - BTN_H / 2))

# ---------------- 画图 ----------------
img = Image.new("RGB", (W, H), (58, 44, 30))
d = ImageDraw.Draw(img)

fp = None
for cand in ("KingdomRushDove/_assets/all-desktop/fonts/msyh.ttc",
             "../KingdomRushDove/_assets/all-desktop/fonts/msyh.ttc"):
    if os.path.exists(cand):
        fp = cand
        break


def font(sz):
    if fp:
        try:
            return ImageFont.truetype(fp, sz)
        except Exception:
            pass
    return ImageFont.load_default()


COLORS = {"main": ((150, 200, 255), None), "slot": ((255, 190, 110), None)}
for layer, n, x, y, w, h in elems:
    o, f = COLORS[layer]
    d.rectangle([x, y, x + w, y + h], outline=o, fill=f, width=2)
for nq, x, y, w, h in rows:
    d.rectangle([x, y, x + w, y + h], outline=(120, 200, 140), width=1)
d.rectangle([0, 0, W - 1, H - 1], outline=(230, 230, 230), width=3)
for layer, n, x, y, w, h in elems:
    if layer == "main":
        d.text((x + 4, y + 3), n, font=font(15), fill=(255, 255, 255))
d.text((6, H - 20),
       "kr6_powers room layout v2 (KR6 assets)  %dx%d" % (W, H),
       font=font(12), fill=(200, 200, 200))

out = "_kr6_room_layout2.png"
img.save(out)
print("\n示意图: %s" % os.path.abspath(out))
