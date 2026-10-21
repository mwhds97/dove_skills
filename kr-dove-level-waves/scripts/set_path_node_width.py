r"""把自建关卡的「路径节点宽度」统一改成指定值（同时改编辑器数据层与烘焙好的几何）。

为什么必须改两处（读源码定的，别只改一处）：
  * `curves[i].widths`  = 编辑器里每个节点（user_point）的宽度。默认 40
    （`all/game_editor.lua:65 DEFAULT_PATH_WIDTH = 40`）。**运行时完全不读它**
    （`path_db:load` 只 merge `path_list.paths`）。
  * `paths[pi][1..3]`   = 编辑器保存时由 `P:generate_paths()`（`all/path_db.lua:818-866`）
    从 curves 烘焙出来的几何：`[1]` = 中心线，`[2]/[3]` = 中心线 ± 宽度/2 的左右边界。
    运行时敌人就是在这几条子路径里随机挑一条走
    （`all/systems/wave_spawn.lua:55` `e.nav_path.spi = ... random(#path)`），
    所以「宽度」在游戏里的表现 = 这几条子路径之间的间距 —— 只改 widths 不改 paths，游戏里毫无变化。

本脚本的做法：中心线一个字节都不动，只把 [2..n] 相对 [1] 的偏移量按 new_w/old_w 缩放，
所以**点数、点索引、node 编号全部保持原样**（这点很关键：航线/波次配置都按 node 索引引用）。
数学上只有在各点宽度**完全一致**时才等价于重新跑 generate_paths；宽度不一致时请改用编辑器重存。

用法:
    python .workbuddy/set_path_node_width.py <paths.lua> <新宽度> [--apply]
    不带 --apply 只干跑并打印报告，不写文件。
"""

import datetime
import math
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_level_bg import load_lua  # noqa: E402  复用纯 Python 的 Lua 数据表解析器

POINT_RE = re.compile(r"^(\t+)v\((-?\d+(?:\.\d+)?), (-?\d+(?:\.\d+)?)\),\s*$")
WIDTH_VAL_RE = re.compile(r"^(\t+)(\d+(?:\.\d+)?),\s*$")


def round_half_up(v):
    """对齐 lib/klua/macros.lua:64 ROUND = math.floor(value + 0.5)。"""
    return math.floor(v + 0.5)


def fmt(v):
    n = round_half_up(v)
    return str(int(n))


def transform(path, new_w, apply=False):
    with open(path, "r", encoding="utf-8-sig") as f:
        raw = f.read()
    lines = raw.split("\n")

    # ── 1. 找 widths 块 ──
    width_blocks = []          # (起始行, 结束行, [值行...])
    i = 0
    while i < len(lines):
        if lines[i].strip() == "widths = {":
            j = i + 1
            vals = []
            while j < len(lines) and lines[j].strip() != "},":
                m = WIDTH_VAL_RE.match(lines[j])
                if m:
                    vals.append(j)
                j += 1
            width_blocks.append((i, j, vals))
            i = j
        i += 1

    # ── 2. 找 paths 段，按缩进状态机定位 组 / 子路径 / 点 ──
    p_start = next((k for k, l in enumerate(lines) if l == "\tpaths = {"), None)
    if p_start is None:
        raise SystemExit("没找到 `\tpaths = {` 段")
    p_end = next((k for k in range(p_start + 1, len(lines)) if lines[k] == "\t},"), None)
    if p_end is None:
        raise SystemExit("没找到 paths 段的结尾 `\t},`")

    groups = {}                # (pi, spi) -> [(行号, x, y), ...]
    pi = spi = 0
    for k in range(p_start + 1, p_end):
        line = lines[k]
        if line == "\t\t{":
            pi += 1
            spi = 0
        elif line == "\t\t\t{":
            spi += 1
        elif (m := POINT_RE.match(line)) and spi:
            groups.setdefault((pi, spi), []).append((k, float(m.group(2)), float(m.group(3))))

    # ── 3. 前置校验 ──
    old_ws = set()
    for _, _, vals in width_blocks:
        for k in vals:
            old_ws.add(float(WIDTH_VAL_RE.match(lines[k]).group(2)))
    if not width_blocks:
        raise SystemExit("没有 widths 块 —— 这个关卡用的是别的口径？")
    if len(old_ws) != 1:
        raise SystemExit(
            "各节点宽度不一致 %s —— 本脚本的等比缩放不适用，请在编辑器里改宽后重新保存"
            % sorted(old_ws))
    old_w = old_ws.pop()
    if old_w == new_w:
        raise SystemExit("旧宽度已经是 %g，无需改动" % new_w)

    ratio = new_w / old_w
    print("旧宽度 %g → 新宽度 %g（缩放系数 %.6f）" % (old_w, new_w, ratio))
    print("widths 块 %d 个，共 %d 个节点值" % (len(width_blocks), sum(len(v) for _, _, v in width_blocks)))

    n_groups = max(p for p, _ in groups)
    total_pts = 0
    max_dev = 0.0
    for p in range(1, n_groups + 1):
        n_sub = max(s for pp, s in groups if pp == p)
        center = groups[(p, 1)]
        widths_per_sub = {s: len(groups[(p, s)]) for s in range(1, n_sub + 1)}
        if len(set(widths_per_sub.values())) != 1:
            raise SystemExit("路径组 %d 各子路径点数不一致 %s，拒绝改动" % (p, widths_per_sub))
        line = "  路径组%d: 子路径 %d 条 × %d 点" % (p, n_sub, len(center))
        if n_sub > 1:
            # 记录一下改动幅度（子路径 2 的偏移长度应约等于 旧宽度/2）
            off = math.dist((center[0][1], center[0][2]),
                            (groups[(p, 2)][0][1], groups[(p, 2)][0][2]))
            line += "，[2] 与 [1] 间距 %.2f → %.2f" % (off, off * ratio)
        print(line)

        for s in range(2, n_sub + 1):
            for idx in range(len(center)):
                k, x, y = groups[(p, s)][idx]
                cx, cy = center[idx][1], center[idx][2]
                nx, ny = cx + (x - cx) * ratio, cy + (y - cy) * ratio
                if apply:
                    indent = POINT_RE.match(lines[k]).group(1)
                    lines[k] = "%sv(%s, %s)," % (indent, fmt(nx), fmt(ny))
                total_pts += 1
                # 与缩放后应有位置的理论偏差（只来自旧数据本身的取整）
                max_dev = max(max_dev, abs(round_half_up(nx) - nx), abs(round_half_up(ny) - ny))

    print("重写子路径点 %d 个（中心线未动），单点取整偏差 ≤ %.2f px" % (total_pts, max_dev))

    if apply:
        for _, _, vals in width_blocks:
            for k in vals:
                indent = WIDTH_VAL_RE.match(lines[k]).group(1)
                lines[k] = "%s%g," % (indent, new_w)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        bak_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups")
        os.makedirs(bak_dir, exist_ok=True)
        bak = os.path.join(bak_dir, "%s.%s.bak" % (os.path.basename(path), stamp))
        shutil.copy2(path, bak)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines))
        print("已写入 %s\n备份 %s" % (path, bak))
    else:
        print("（干跑，未写文件；加 --apply 才落盘）")
    return ratio


def verify(path, new_w, bak=None):
    """改完自检：点数不变、边界间距 = 新宽度/2、widths 全是新值。

    注意 Lua 数组下标从 1 开始；点解析成 `("call", "v", [x, y])` 元组。
    """
    d = load_lua(path)
    groups = [g.array for g in d["paths"].array]

    def pt(sub, i):  # i 为 1-based，与引擎里 node 编号一致
        p = sub[i]
        return (p[2][0], p[2][1])

    print("\n== 自检 ==")
    ok = True
    for pi, subs in enumerate(groups, 1):
        lens = [len(s.array) for s in subs]
        if len(set(lens)) != 1:
            print("  FAIL 组%d 各子路径点数不一致 %s" % (pi, lens))
            ok = False
            continue
        n = lens[0]
        ds = [math.dist(pt(subs[0], i), pt(subs[s], i))
              for s in range(1, len(subs)) for i in range(1, n + 1)]
        lo, hi = min(ds), max(ds)
        good = abs(lo - new_w / 2) < 1.5 and abs(hi - new_w / 2) < 1.5
        print("  %s 组%d: %d 点 × %d 子路径，边界间距 %.2f~%.2f（目标 %.1f）"
              % ("OK  " if good else "FAIL", pi, n, len(subs), lo, hi, new_w / 2))
        ok = ok and good
    ws = sorted({w for c in d["curves"].array for w in c["widths"].array})
    print("  %s widths 取值集合 = %s" % ("OK  " if ws == [new_w] else "FAIL", ws))
    return ok and ws == [new_w]


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    path, new_w = sys.argv[1], float(sys.argv[2])
    apply = "--apply" in sys.argv
    transform(path, new_w, apply)
    if apply:
        if not verify(path, new_w):
            raise SystemExit("自检未通过，请检查备份并回滚")
        print("\n自检全部通过")


if __name__ == "__main__":
    main()
