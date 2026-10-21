#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 Tropical_Loop 的 16 波出怪（编译态 + 编辑器配置态）。

规则对齐 dove_modules/wave_generator/interface.lua：
  - 每子波只放 1 个兵种，且 weight = 该子波期望金币，total_gold = Σ weight
    → distribute_total_amount_to_groups_randomly 退化为确定拆分（floor 无损）
  - 子波金币 gold → 数量 = ceil(gold / enemy.gold)，所以 gold = count * 单价 即得精确数量
  - 子波时长(帧) = (group.interval - delay - rest) * 30
编译态排版照抄用户原文件：键按字母序、制表符缩进、每只 1 个 max=1 条目 + max=0 空档条目。
"""
import math
import os
import re
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
ROOT = PROJECT
PLUGIN_WS = os.path.join(ROOT, "KingdomRushDove", "mods", "local", "Tropical_Loop")
PLUGIN_AD = os.path.join(os.environ.get("APPDATA", ""), "LOVE", "kingdom_rush_dove",
                          "plugins", "Tropical_Loop")

GOLD = {
    "enemy_fat_orc": 9, "enemy_brigand": 15, "enemy_bandit": 8, "enemy_wolf": 12,
    "enemy_jungle_spider_small": 8, "enemy_orc_armored": 30, "enemy_gargoyle": 12,
    "enemy_ogre": 50, "enemy_cannibal": 15, "enemy_hunter": 15, "enemy_marauder": 40,
    "enemy_shaman": 10, "enemy_jungle_spider_big": 40, "enemy_wasp": 8,
    "enemy_orc_rider": 25, "enemy_shaman_priest": 50, "enemy_raider": 50,
    "enemy_gorilla": 160, "enemy_pillager": 100, "enemy_shaman_shield": 50,
    "enemy_savage_bird_rider": 25, "enemy_shaman_magic": 50, "enemy_shaman_necro": 50,
    "enemy_forest_troll": 200,
}
NAME_CN = {
    "enemy_fat_orc": "兽人", "enemy_brigand": "土匪", "enemy_bandit": "强盗",
    "enemy_wolf": "座狼", "enemy_jungle_spider_small": "丛林蜘蛛", "enemy_orc_armored": "兽人勇士",
    "enemy_gargoyle": "石像鬼", "enemy_ogre": "食人魔", "enemy_cannibal": "野蛮人战士",
    "enemy_hunter": "野蛮人猎人", "enemy_marauder": "掠夺者", "enemy_shaman": "萨满",
    "enemy_jungle_spider_big": "丛林蜘蛛女王", "enemy_wasp": "巨型黄蜂",
    "enemy_orc_rider": "座狼骑兵", "enemy_shaman_priest": "巫医", "enemy_raider": "侵袭者",
    "enemy_gorilla": "大猩猩", "enemy_pillager": "强夺者", "enemy_shaman_shield": "大地萨满",
    "enemy_savage_bird_rider": "巨鸟骑士", "enemy_shaman_magic": "精神萨满",
    "enemy_shaman_necro": "血祭巫医", "enemy_forest_troll": "森林巨魔",
}
FLYING = {"enemy_gargoyle", "enemy_wasp", "enemy_savage_bird_rider"}
# 死亡召唤 1 只额外单位（统计总出怪时单独算）
SUMMON = {"enemy_orc_rider": "enemy_orc_armored_mad", "enemy_savage_bird_rider": "enemy_savage_bird"}

LIVES, CASH = 20, 1000

# (delay, rest, path_index, enemy, count, [显式分阵型] or None)
# 第 1 波 = 用户原样，分阵型与空档照抄
W1 = (33, 240, [
    (0, 5, 1, "enemy_fat_orc", 14,
     ([[1, 2, 3], [1, 2, 3], [1, 2, 3], [1], [2, 3], [2, 3]], [87, 196, 181, 177, 199])),
    (20, 5, 4, "enemy_brigand", 8,
     ([[1, 2, 3], [1], [1, 2, 3], [1]], [63, 76, 101])),
])

WAVES = [
    (32, [(0, 4, 1, "enemy_bandit", 12, None), (10, 4, 2, "enemy_wolf", 8, None)]),
    (36, [(0, 5, 3, "enemy_brigand", 10, None), (12, 5, 4, "enemy_jungle_spider_small", 12, None)]),
    (36, [(0, 5, 1, "enemy_orc_armored", 10, None), (14, 5, 2, "enemy_bandit", 12, None)]),
    (40, [(0, 4, 1, "enemy_gargoyle", 6, None), (8, 4, 2, "enemy_wolf", 8, None),
          (18, 4, 4, "enemy_orc_armored", 8, None)]),
    (40, [(0, 4, 1, "enemy_ogre", 6, None), (12, 4, 2, "enemy_brigand", 18, None)]),
    (38, [(0, 4, 3, "enemy_cannibal", 14, None), (10, 4, 4, "enemy_hunter", 10, None)]),
    (42, [(0, 4, 1, "enemy_marauder", 6, None), (10, 4, 2, "enemy_shaman", 4, None),
          (20, 4, 4, "enemy_orc_armored", 12, None)]),
    (40, [(0, 4, 1, "enemy_jungle_spider_big", 6, None), (8, 4, 2, "enemy_wasp", 6, None),
          (16, 4, 3, "enemy_jungle_spider_small", 10, None)]),
    (42, [(0, 4, 1, "enemy_orc_rider", 6, None), (12, 4, 2, "enemy_orc_armored", 10, None),
          (22, 4, 4, "enemy_shaman_priest", 4, None)]),
    (44, [(0, 4, 1, "enemy_raider", 8, None), (12, 4, 2, "enemy_marauder", 10, None),
          (22, 4, 4, "enemy_shaman", 4, None)]),
    (42, [(0, 5, 1, "enemy_gorilla", 3, None), (12, 5, 2, "enemy_cannibal", 15, None)]),
    (44, [(0, 4, 1, "enemy_pillager", 4, None), (12, 4, 2, "enemy_shaman_shield", 4, None),
          (22, 4, 4, "enemy_marauder", 8, None)]),
    (44, [(0, 4, 1, "enemy_savage_bird_rider", 4, None), (12, 4, 2, "enemy_shaman_magic", 4, None),
          (22, 4, 4, "enemy_shaman_necro", 6, None)]),
    (46, [(0, 5, 1, "enemy_forest_troll", 3, None), (14, 5, 2, "enemy_orc_armored", 11, None)]),
    (55, [(0, 5, 1, "enemy_forest_troll", 3, None), (12, 5, 2, "enemy_gorilla", 3, None),
          (22, 5, 4, "enemy_pillager", 4, None), (32, 5, 3, "enemy_shaman_priest", 3, None),
          (40, 5, 4, "enemy_shaman_magic", 3, None)]),
]


def split_bursts(count, window_frames):
    """把 count 只摊成若干阵型小组（每组最多 3 只，路径 1/2/3），返回 (sizes, gaps)。"""
    n_by_size = int(math.ceil(count / 3.0))
    n_by_pace = max(1, int(round(window_frames / 30.0 / 7.0)))
    n = max(n_by_size, min(count, n_by_pace))
    n = min(n, count)
    base, extra = divmod(count, n)
    sizes = [base + (1 if i < extra else 0) for i in range(n)]
    sizes.sort(reverse=True)
    gaps = []
    if n > 1:
        each, rem = divmod(window_frames, n - 1)
        gaps = [each] * (n - 1)
        gaps[-1] += rem
    return sizes, gaps


def bursts_to_pairs(sizes):
    """阵型小组 → 该组占用哪些子路径。"""
    return [list(range(1, s + 1)) for s in sizes]


def build_group(index, interval_sec, waves_spec, explicit=None):
    """返回 (compiled_group, config_group, 统计)"""
    waves, cfgs = [], []
    for delay, rest, path_index, enemy, count, explicit_arr in waves_spec:
        window = (interval_sec - delay - rest) * 30
        if explicit_arr:
            bursts, gaps = explicit_arr[0], explicit_arr[1]
        else:
            sizes, gaps = split_bursts(count, window)
            bursts = [[1, 2, 3] if s == 3 else [2, 3] if s == 2 else [1] for s in sizes]
        spawns = []
        for bi, paths in enumerate(bursts):
            for p in paths:
                spawns.append(("unit", enemy, p, 0))
            if bi < len(gaps):
                spawns.append(("gap", enemy, 1, gaps[bi]))
        waves.append({
            "delay": delay * 30, "path_index": path_index,
            "some_flying": enemy in FLYING, "spawns": spawns,
        })
        cfgs.append({"delay": delay, "enemy": enemy, "path_index": path_index,
                     "rest": rest, "weight": count * GOLD[enemy]})
    total_gold = sum(c["weight"] for c in cfgs)
    compiled = {"interval": interval_sec * 30, "waves": waves}
    config = {"interval": interval_sec, "total_gold": total_gold, "waves": cfgs}
    return compiled, config


def render_compiled(groups):
    L = ["return {", "\tcash = %d," % CASH, "\tgroups = {"]
    for g in groups:
        L.append("\t\t{")
        L.append("\t\t\tinterval = %d," % g["interval"])
        L.append("\t\t\twaves = {")
        for w in g["waves"]:
            L.append("\t\t\t\t{")
            L.append("\t\t\t\t\tdelay = %d," % w["delay"])
            L.append("\t\t\t\t\tpath_index = %d," % w["path_index"])
            L.append("\t\t\t\t\tsome_flying = %s," % ("true" if w["some_flying"] else "false"))
            L.append("\t\t\t\t\tspawns = {")
            for kind, creep, path, gap in w["spawns"]:
                L.append("\t\t\t\t\t\t{")
                L.append('\t\t\t\t\t\t\tcreep = "%s",' % creep)
                L.append("\t\t\t\t\t\t\tfixed_sub_path = %d," % (1 if kind == "unit" else 0))
                L.append("\t\t\t\t\t\t\tinterval = %d," % (0 if kind == "unit" else gap))
                L.append("\t\t\t\t\t\t\tinterval_next = 0,")
                L.append("\t\t\t\t\t\t\tmax = %d," % (1 if kind == "unit" else 0))
                L.append("\t\t\t\t\t\t\tmax_same = 0,")
                L.append("\t\t\t\t\t\t\tpath = %d," % path)
                L.append("\t\t\t\t\t\t},")
            L.append("\t\t\t\t\t},")
            L.append("\t\t\t\t},")
        L.append("\t\t\t},")
        L.append("\t\t},")
    L.append("\t},")
    L.append("\tlives = %d," % LIVES)
    L.append("}")
    return "\n".join(L) + "\n"


def render_config(groups):
    L = ["return {", "\tcash = %d," % CASH, "\tgroups = {"]
    for g in groups:
        L.append("\t\t{")
        L.append("\t\t\tinterval = %d," % g["interval"])
        L.append("\t\t\ttotal_gold = %d," % g["total_gold"])
        L.append("\t\t\twaves = {")
        for w in g["waves"]:
            L.append("\t\t\t\t{")
            L.append("\t\t\t\t\tdelay = %d," % w["delay"])
            L.append("\t\t\t\t\tenemies = {")
            L.append('\t\t\t\t\t\t"%s",' % w["enemy"])
            L.append("\t\t\t\t\t},")
            L.append("\t\t\t\t\tformation = true,")
            L.append("\t\t\t\t\tpath_index = %d," % w["path_index"])
            L.append("\t\t\t\t\trest = %d," % w["rest"])
            L.append("\t\t\t\t\tweight = %d," % w["weight"])
            L.append("\t\t\t\t},")
        L.append("\t\t\t},")
        L.append("\t\t},")
    L.append("\t},")
    L.append("\tlives = %d," % LIVES)
    L.append("}")
    return "\n".join(L) + "\n"


def main():
    ng, nc = build_group(1, W1[0], W1[2])
    groups_c, groups_cfg = [ng], [nc]
    for i, (interval, spec) in enumerate(WAVES, start=2):
        gc, gcf = build_group(i, interval, spec)
        groups_c.append(gc)
        groups_cfg.append(gcf)

    # 第 1 波完全沿用用户原配置：total_gold 240、weight 1/1（拆分仍是 120+120，数量不变）
    groups_cfg[0]["total_gold"] = W1[1]
    for w in groups_cfg[0]["waves"]:
        w["weight"] = 1

    # 统计
    total_units, total_summon, total_gold = 0, 0, 0
    print("波次  间隔  子波  兵种(数量)                          子波总数  本波金币")
    for i, (g, gc) in enumerate(zip(groups_c, groups_cfg), start=1):
        n, summon, txt = 0, 0, []
        for w in g["waves"]:
            cnt = sum(1 for s in w["spawns"] if s[0] == "unit")
            n += cnt
            summon += cnt if w["spawns"][0][1] in SUMMON else 0
            txt.append("%s×%d@p%d" % (NAME_CN[w["spawns"][0][1]], cnt, w["path_index"]))
        total_units += n
        total_summon += summon
        total_gold += gc["total_gold"]
        print("W%-3d  %3ds   %-3d  %-38s  %-8d  %d" % (
            i, g["interval"] // 30, len(g["waves"]), " ".join(txt), n, gc["total_gold"]))
    print("-" * 78)
    print("固定出怪 %d 只 + 死亡召唤 %d 只 = 场上合计 %d 只（上限 340）"
          % (total_units, total_summon, total_units + total_summon))
    print("全程金币总量 %d（含击杀回收）" % total_gold)

    outs = [
        (os.path.join(PLUGIN_WS, "data", "waves", "Tropical_Loop_waves_campaign.lua"), render_compiled(groups_c)),
        (os.path.join(PLUGIN_WS, "data", "waveconfigs", "Tropical_Loop_waves_campaign_config.lua"), render_config(groups_cfg)),
    ]
    for path, text in outs:
        open(path, "w", encoding="utf-8", newline="\n").write(text)
        print("written", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
