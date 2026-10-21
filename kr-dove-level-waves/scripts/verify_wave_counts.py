# -*- coding: utf-8 -*-
"""模拟 dove_modules/wave_generator/interface.lua 的确定性部分，
验证「配置态 → 编辑器重新生成」得到的数量与手写编译态一致。"""
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
WS = os.path.join(ROOT, "KingdomRushDove", "mods", "local", "Tropical_Loop", "data")
GOLD = {"enemy_fat_orc": 9, "enemy_brigand": 15, "enemy_bandit": 8, "enemy_wolf": 12,
        "enemy_jungle_spider_small": 8, "enemy_orc_armored": 30, "enemy_gargoyle": 12,
        "enemy_ogre": 50, "enemy_cannibal": 15, "enemy_hunter": 15, "enemy_marauder": 40,
        "enemy_shaman": 10, "enemy_jungle_spider_big": 40, "enemy_wasp": 8,
        "enemy_orc_rider": 25, "enemy_shaman_priest": 50, "enemy_raider": 50,
        "enemy_gorilla": 160, "enemy_pillager": 100, "enemy_shaman_shield": 50,
        "enemy_savage_bird_rider": 25, "enemy_shaman_magic": 50, "enemy_shaman_necro": 50,
        "enemy_forest_troll": 200}


def distribute(total, n, min_each=0, weights=None):
    """lua 端 distribute_total_amount_to_groups_randomly 的确定性等价实现"""
    remain = total - min_each * n
    ws = list(weights) if weights else [1.0] * n
    s = sum(ws)
    res = [min_each + math.floor(remain * w / s) for w in ws]
    diff = total - sum(res)
    if diff > 0:
        order = sorted(range(n), key=lambda i: -ws[i])
        for i in range(diff):
            res[order[i % n]] += 1
    return res


def parse_config(path):
    src = open(path, encoding="utf-8").read()
    groups = []
    # 按 groups 块内的一级 { } 切分
    gi = src.index("groups = {")
    depth, i = 0, src.index("{", gi)
    start = i
    while i < len(src):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    block = src[start:i + 1]
    # 顶层每个 group 是 depth==2 的区间
    depth, cur, out = 0, None, []
    for ch in block:
        if ch == "{":
            depth += 1
            if depth == 2:
                cur = []
            elif cur is not None:
                cur.append(ch)
        elif ch == "}":
            if depth == 2:
                out.append("".join(cur))
                cur = None
            elif cur is not None:
                cur.append(ch)
            depth -= 1
        elif cur is not None:
            cur.append(ch)
    for g in out:
        interval = int(re.search(r"interval\s*=\s*(\d+)", g).group(1))
        total_gold = int(re.search(r"total_gold\s*=\s*(\d+)", g).group(1))
        waves = []
        for w in re.findall(r"delay\s*=\s*(\d+),\s*enemies\s*=\s*\{([^}]*)\}"
                            r",\s*formation\s*=\s*true,\s*path_index\s*=\s*(\d+),"
                            r"\s*rest\s*=\s*(\d+),\s*weight\s*=\s*(\d+)", g):
            waves.append({"delay": int(w[0]), "enemy": re.findall(r'"([^"]+)"', w[1])[0],
                          "path_index": int(w[2]), "rest": int(w[3]), "weight": int(w[4])})
        groups.append({"interval": interval, "total_gold": total_gold, "waves": waves})
    return groups


def parse_compiled(path):
    src = open(path, encoding="utf-8").read()
    groups = []
    depth, i = 0, src.index("groups = {")
    start = src.index("{", i)
    i = start
    while i < len(src):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    block = src[start:i + 1]
    depth, cur, out = 0, None, []
    for ch in block:
        if ch == "{":
            depth += 1
            if depth == 2:
                cur = []
            elif cur is not None:
                cur.append(ch)
        elif ch == "}":
            if depth == 2:
                out.append("".join(cur))
                cur = None
            elif cur is not None:
                cur.append(ch)
            depth -= 1
        elif cur is not None:
            cur.append(ch)
    for g in out:
        interval = int(re.search(r"interval\s*=\s*(\d+)", g).group(1))
        waves = []
        for wblock in re.split(r"path_index\s*=", g)[1:]:
            pi = int(wblock.split(",")[0])
            spawns = re.findall(r'creep\s*=\s*"([^"]+)"[^}]*?max\s*=\s*(\d+)', wblock)
            units = [(c, int(m)) for c, m in spawns if int(m) > 0]
            waves.append({"path_index": pi, "units": units})
        groups.append({"interval": interval, "waves": waves})
    return groups


def main():
    cfg = parse_config(os.path.join(WS, "waveconfigs", "Tropical_Loop_waves_campaign_config.lua"))
    comp = parse_compiled(os.path.join(WS, "waves", "Tropical_Loop_waves_campaign.lua"))
    assert len(cfg) == len(comp), "组数不一致 %d vs %d" % (len(cfg), len(comp))

    ok = True
    tot_cfg = tot_comp = 0
    print("波次  配置推导数量                     手写编译态数量                   一致")
    for idx, (c, p) in enumerate(zip(cfg, comp), start=1):
        golds = distribute(c["total_gold"], len(c["waves"]), 0,
                           [w["weight"] for w in c["waves"]])
        exp, got = [], []
        for w, gld in zip(c["waves"], golds):
            cnt = math.ceil(gld / GOLD[w["enemy"]])
            exp.append((w["enemy"], cnt, w["path_index"]))
        if c["interval"] != p["interval"] // 30:
            print("  !! W%d interval 不一致 %d vs %d" % (idx, c["interval"], p["interval"] // 30))
            ok = False
        agg = {}
        for wb in p["waves"]:
            for cr, m in wb["units"]:
                key = (cr, wb["path_index"])
                agg[key] = agg.get(key, 0) + m
        got = [(cr, m, pi) for (cr, pi), m in agg.items()]
        same = sorted(exp) == sorted(got)
        ok = ok and same
        tot_cfg += sum(e[1] for e in exp)
        tot_comp += sum(g[1] for g in got)
        f = lambda lst: " ".join("%s×%d@p%d" % t for t in lst)
        print("W%-3d  %-34s %-34s %s" % (idx, f(exp), f(got), "OK" if same else "差异!"))
    print("-" * 88)
    print("配置推导合计 %d 只 / 编译态合计 %d 只" % (tot_cfg, tot_comp))
    print("结论：%s" % ("编辑器重新生成不会改变数量 ✓" if ok and tot_cfg == tot_comp else "存在差异 ✗"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
