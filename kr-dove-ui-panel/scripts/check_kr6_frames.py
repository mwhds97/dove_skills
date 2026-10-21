# -*- coding: utf-8 -*-
"""kr6_powers 帧名体检：检查插件引用的每个「帧名」是否真的存在于 Dove 图集里。

⭐⭐ 为什么必须有这个（踩过两次，每次都是用户实机才发现）：
  · **离线 love_stub 不加载 KRAB 二进制索引** ⇒ 静态 grep 查帧名全是假阴性
    （连本体自己在用的帧都查不到）
  · **KR6 与 Dove 同功能帧常常不同前缀**，抄 KR6 名就崩：
      头像  KR6 `gui_bottom_info_image_soldiers_0068`
            Dove `kr6_info_portraits_soldiers_0068`（编号一一对应）
      即死  KR6 `pop_headshot` / Dove `pop_instakill`
  · 崩溃表现（很晚才发现、且报错点在引擎里）：
      `kui.lua:529 attempt to index local 'ss' (a nil value)`
      `image_db.error Sprite <帧名> was not found in the atlas db.`

用法：python .workbuddy/check_kr6_frames.py
退出码 0 = 全过；1 = 有可疑帧名（需人工确认是帧还是模板名）。
"""

import io
import json
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
PLUG = os.path.join(PROJECT, "mods", "local", "kr6_powers")
IDX = os.environ.get("KRAB_INDEX", os.path.join(PROJECT, ".workbuddy", "_krab_index.json"))

# 「值是帧名」的字段（其余字段的值是模板名/脚本名，不该按帧名查）
FRAME_FIELDS = [
    "info.portrait", "bullet.hit_fx", "bullet.hit_payload", "bullet.pop",
    "aura.mod", "aura.mod_", "aura_in_t", "aura_buff_t",
    "decal_beam", "decal_smoke", "decal_crack", "decal_splash", "spawn_aura",
    "melee.attacks[1].hit_fx", "hit_fx", "casing", "image_name",
    "default_image_name", "hover_image_name", "click_image_name",
]

# 已知的「同功能但 Dove 前缀不同」映射（人工比对 + 像素验证得出）
# 键 = KR6 名，值 = Dove 名。插件里若出现 KR6 名 ⇒ 报错并给出替代。
KR6_ONLY_NAMES = {
    "gui_bottom_info_image_soldiers_": "kr6_info_portraits_soldiers_",  # 头像
    "pop_headshot": "pop_instakill",                                    # 即死爆头
}

# 例外：这些值不是帧名（是模板名/脚本名/动画前缀），跳过
SKIP_PREFIXES = ("kr6_powers_", "scripts.", "kr_", "fx_", "aura_", "mod_",
                 "decal_", "bullet_", "power_", "soldier_", "pop_")
SKIP_EXACT = set()


def load_index():
    if not os.path.exists(IDX):
        print("缺索引缓存 ⇒ 先跑：python .workbuddy/_krab_check.py --rebuild")
        return None
    with io.open(IDX, encoding="utf-8") as f:
        return json.load(f)


def prefix_set(idx):
    """动画前缀集合：`kr6_sol_decal_0017` → `kr6_sol_decal`。

    ⚠ 引擎里 `render.sprites[1].prefix` 存的是**前缀**（动画键 = prefix .. "_" .. name，
    all/systems/render.lua:398）⇒ 只查完整帧名会把合法的前缀误报成缺失。
    """
    out = set()
    for k in idx:
        i = k.rfind("_")
        if i > 0 and k[i + 1:].isdigit():
            out.add(k[:i])
    return out


def main():
    idx = load_index()
    if idx is None:
        return 1
    pref = prefix_set(idx)

    pat = re.compile(
        r"(?:%s)\s*=\s*(.+?)(?:\n|$)" % "|".join(re.escape(f) for f in FRAME_FIELDS))
    bad_kr6 = []      # 用了 KR6 专有名（有已知 Dove 替代）
    unknown = []      # 既不在图集里、也不在例外名单（需人工判断）

    for fn in sorted(os.listdir(PLUG)):
        if not fn.endswith(".lua"):
            continue
        s = io.open(os.path.join(PLUG, fn), encoding="utf-8").read()
        # 剥注释，避免命中自己写的说明文字
        s = re.sub(r"--[^\n]*", "", s)
        for m in pat.finditer(s):
            for lit in re.findall(r'"([A-Za-z0-9_]+)"', m.group(1)):
                for kr6n, dven in KR6_ONLY_NAMES.items():
                    if lit.startswith(kr6n) or lit == kr6n:
                        bad_kr6.append((lit, dven, fn))
                if lit in idx or lit in pref:
                    continue
                if lit in SKIP_EXACT or lit.startswith(SKIP_PREFIXES):
                    continue
                unknown.append((lit, fn))

    print("=== ① 不得使用 KR6 专有帧名（Dove 前缀不同）===")
    if bad_kr6:
        for lit, dven, fn in bad_kr6:
            print("  ⛔ %-46s ⇒ 应改为 %s   [%s]" % (lit, dven, fn))
    else:
        print("  ✓ 无")

    print()
    print("=== ② 帧名是否真的存在于 Dove 图集 ===")
    if unknown:
        for lit, fn in unknown:
            print("  ?  %-46s 图集里查不到，需人工确认是帧还是模板名   [%s]" % (lit, fn))
    else:
        print("  ✓ 全部命中")

    print()
    if bad_kr6:
        print("=== 失败：发现 KR6 专有帧名（会崩 kui.lua:529）===")
        return 1
    if unknown:
        print("=== 注意：%d 个名字待人工判断（若确认是模板名可加进 SKIP 名单）===" % len(unknown))
        return 1
    print("=== 帧名体检全部通过 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
