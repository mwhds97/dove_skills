# -*- coding: utf-8 -*-
"""Extract enemy template stats for KR Dove levels 17 & 37."""
import re, os, json

import os

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
ROOT = os.path.join(PROJECT, "KingdomRushDove")
KR = os.path.join(ROOT, "kr1")

L17 = ["eb_kingpin","enemy_bandit","enemy_brigand","enemy_gargoyle","enemy_marauder",
       "enemy_pillager","enemy_raider","enemy_spider_big","enemy_spider_small",
       "enemy_wolf","enemy_wolf_small"]
L37 = ["enemy_cannibal","enemy_gorilla","enemy_hunter","enemy_jungle_spider_big",
       "enemy_jungle_spider_small","enemy_savage_bird_rider","enemy_shaman_magic",
       "enemy_shaman_necro","enemy_shaman_priest","enemy_shaman_rage",
       "enemy_shaman_shield","enemy_wasp"]
TARGETS = L17 + L37

# ---------- 1. 定位每个模板的 RT 定义 ----------
def collect_blocks():
    files = []
    for fn in os.listdir(KR):
        if fn.endswith(".lua"):
            files.append(os.path.join(KR, fn))
    blocks = {}   # name -> (file, blocktext)
    for path in files:
        try:
            s = open(path, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        for m in re.finditer(r'RT\(\s*"([a-zA-Z0-9_]+)"', s):
            name = m.group(1)
            start = m.end()
            nxt = s.find('RT("', start)
            nxt2 = s.find("RT( '", start)
            end = len(s)
            if nxt != -1:
                end = min(end, nxt)
            if nxt2 != -1:
                end = min(end, nxt2)
            blk = s[start:end]
            if name not in blocks:
                blocks[name] = (os.path.basename(path), blk)
    return blocks

BLOCKS = collect_blocks()

# ---------- 2. 提取字段 ----------
def field(blk, key):
    """返回最后一次赋值（可能是表）。"""
    pat = re.escape(key) + r'\s*=\s*([^\n]+)'
    vals = re.findall(pat, blk)
    return vals[-1].strip().rstrip(',') if vals else None

def field_all(blk, key):
    pat = re.escape(key) + r'\s*=\s*([^\n]+)'
    return [v.strip().rstrip(',') for v in re.findall(pat, blk)]

def num(v):
    if v is None:
        return None
    v = v.strip()
    # 处理 {a, b, ...}
    if v.startswith("{"):
        return [x.strip() for x in v.strip("{} ").split(",")]
    m = re.match(r'(-?\d+(?:\.\d+)?)', v)
    return m.group(1) if m else v

# ---------- 3. 中文名 ----------
STR = os.path.join(ROOT, "_assets", "kr1-desktop", "strings", "zh-Hans.lua")
strs = {}
if os.path.exists(STR):
    t = open(STR, encoding="utf-8", errors="ignore").read()
    for m in re.finditer(r'(\w+)\s*=\s*"([^"]*)"', t):
        strs[m.group(1)] = m.group(2)
    # 多行字符串拼接的忽略
def cn_name(tpl):
    for k in ("%s_NAME" % tpl.upper(), "%s_name" % tpl):
        if k in strs:
            return strs[k]
    return "?"

# ---------- 4. 输出 ----------
def report(lst, title):
    print("=" * 78)
    print(title)
    print("=" * 78)
    for tpl in lst:
        if tpl not in BLOCKS:
            print("[缺失] %s  <- 未找到 RT 定义" % tpl)
            continue
        src, blk = BLOCKS[tpl]
        hp   = field(blk, "tt.health.hp_max")
        hpe  = field(blk, "tt.health.hp_max_evolved")
        arm  = field(blk, "tt.health.armor")
        spd  = field(blk, "tt.motion.max_speed")
        gold = field(blk, "tt.enemy.gold")
        life = field(blk, "tt.enemy.lives_cost")
        dmin = field(blk, "tt.melee.attacks[1].damage_min")
        dmax = field(blk, "tt.melee.attacks[1].damage_max")
        cd   = field(blk, "tt.melee.attacks[1].cooldown")
        rmin = field(blk, "tt.ranged.attacks[1].damage_min")
        rmax = field(blk, "tt.ranged.attacks[1].damage_max")
        size = field(blk, "tt.unit.size")
        print("\n%-30s  [%s]" % (tpl, src))
        print("  中文名 : %s" % cn_name(tpl))
        print("  血量   : %s%s" % (num(hp), ("  进化血=%s" % num(hpe)) if hpe else ""))
        print("  护甲   : %s" % num(arm))
        print("  速度   : %s" % num(spd))
        print("  赏金/命: gold=%s lives_cost=%s" % (num(gold), num(life)))
        if dmin or dmax:
            print("  近战   : %s-%s  冷却=%s" % (num(dmin), num(dmax), num(cd)))
        if rmin or rmax:
            print("  远程   : %s-%s" % (num(rmin), num(rmax)))
        print("  体型   : %s" % (num(size) or "-"))

report(L17, "第 17 关 敌方单位")
report(L37, "第 37 关 敌方单位")

# 导出 JSON 供后续使用
out = {}
for tpl in TARGETS:
    if tpl not in BLOCKS:
        continue
    src, blk = BLOCKS[tpl]
    out[tpl] = {
        "source": src,
        "cn": cn_name(tpl),
        "hp": num(field(blk, "tt.health.hp_max")),
        "hp_evolved": num(field(blk, "tt.health.hp_max_evolved")),
        "armor": num(field(blk, "tt.health.armor")),
        "speed": num(field(blk, "tt.motion.max_speed")),
        "gold": num(field(blk, "tt.enemy.gold")),
        "lives_cost": num(field(blk, "tt.enemy.lives_cost")),
        "melee_min": num(field(blk, "tt.melee.attacks[1].damage_min")),
        "melee_max": num(field(blk, "tt.melee.attacks[1].damage_max")),
        "melee_cd": num(field(blk, "tt.melee.attacks[1].cooldown")),
        "ranged_min": num(field(blk, "tt.ranged.attacks[1].damage_min")),
        "ranged_max": num(field(blk, "tt.ranged.attacks[1].damage_max")),
        "size": num(field(blk, "tt.unit.size")),
    }
jp = os.path.join(PROJECT, ".workbuddy", "enemy_stats_17_37.json")
json.dump(out, open(jp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\nJSON 已写出: %s" % jp)
