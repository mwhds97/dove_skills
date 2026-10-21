# -*- coding: utf-8 -*-
"""推导某张自建关卡需要哪些图集组（go_enemies_* / go_stage* ...）。

用法:
  python find_level_atlases.py <KingdomRushDove 根> <该关的 _waves_campaign.lua>

原理:
  1. 波文件里的 creep 名 = 敌人模板名（编译态字段名是 creep）
  2. 帧前缀来源（两级）:
     a. game_animations.lua 里 <模板>_* 动画条目的 prefix（按"最长模板名前缀"归属）
     b. 模板本体 render.sprites[i].prefix / .name（鳄鱼系敌人如 enemy_crocs_basic
        没有 <模板>_idle 这类动画键，帧前缀直接写在 sprites[1].prefix，如 gator_creep）
     c. 模板里引用到的其它模板（tt.bullet = "xxx" / create_entity("ps_xxx") 一类）
        再展开一层，取它们的 sprites 前缀
  3. 在 _assets/kr1-desktop/images/fullhd/go_*.lua 里，用 "[ ,]<名字>_\\d{4} =" 反查所属组
     （同一批水花/特效帧常同时存在于多个组：go_stage121 与 go_stage122 的
      fx_water_* 62 帧美术完全相同，但 121 只有 1 张 8MB dds、122 是 2 张 32MB，
      所以应优先登记体积小的那个组）
  4. 扣掉 all/game.lua 的 game.required_textures（常驻组）

⚠️ 必须按"最长模板名前缀"归属，否则 `enemy_cannibal` 会吞掉 `enemy_cannibal_volcano_*`
（那是 level36 火山关的独立模板 enemy_cannibal_volcano，帧在 go_stage36），导致多加载几十 MB。
"""
import os, re, sys, io


def read(p):
    with io.open(p, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def brace_body(text, start):
    """text[start] 必须是 '{'，返回配对内容。"""
    d, j = 0, start
    while j < len(text):
        if text[j] == '{':
            d += 1
        elif text[j] == '}':
            d -= 1
            if d == 0:
                return text[start + 1:j]
        j += 1
    return ''


def register_blocks(text):
    """返回 {模板名: 模板正文}。正文 = 本 register 到下一个 register 之间。"""
    ms = [(m.start(), m.group(1)) for m in
          re.finditer(r'(?:E:register_t|RT)\(\s*"([^"]+)"', text)]
    out = {}
    for i, (st, nm) in enumerate(ms):
        e = ms[i + 1][0] if i + 1 < len(ms) else len(text)
        out.setdefault(nm, text[st:e])
    return out


def main(root, waves_path):
    # 1) 目标关卡的敌人
    creeps = sorted(set(re.findall(r'creep\s*=\s*"([^"]+)"', read(waves_path))))
    print("distinct creeps: %d" % len(creeps))

    # 2) 常驻图集组
    gm = read(os.path.join(root, r"all\game.lua"))
    mm = re.search(r"game\.required_textures\s*=\s*\{", gm)
    always = set(re.findall(r'"([^"]+)"', brace_body(gm, mm.end() - 1)))

    # 3) 模板表
    tmpl = {}
    for rel in (r"kr1\enemies.lua", r"kr1\boss.lua", r"kr1\game_templates.lua",
                r"all\templates.lua", r"all\scripts.lua"):
        p = os.path.join(root, rel)
        if os.path.exists(p):
            tmpl.update(register_blocks(read(p)))
    tmpl_set = set(tmpl)

    # 4) 动画键 -> 帧前缀（按最长模板名前缀归属，用下划线切分避免 O(模板数) 扫描）
    at = read(os.path.join(root, r"kr1\data\game_animations.lua"))
    entries = {}
    for m in re.finditer(r'\n\t([A-Za-z0-9_]+)\s*=\s*\{', at):
        entries.setdefault(m.group(1), m.end() - 1)

    def owner(key):
        idx = key.rfind("_")
        while idx > 0:
            cand = key[:idx]
            if cand in tmpl_set:
                return cand
            idx = key.rfind("_", 0, idx)
        return None

    prefix_by_tmpl = {}
    for k, pos in entries.items():
        o = owner(k)
        if not o:
            continue
        b = brace_body(at, pos)
        for p in re.findall(r'prefix\s*=\s*"([^"]+)"', b):
            prefix_by_tmpl.setdefault(o, set()).add(p)

    # 5) 帧前缀 -> 图集组（一次读盘建索引）
    fullhd = os.path.join(root, r"_assets\kr1-desktop\images\fullhd")
    prefix_groups = {}
    for fn in os.listdir(fullhd):
        if not (fn.startswith("go_") and fn.endswith(".lua")):
            continue
        txt = read(os.path.join(fullhd, fn))
        g = fn[:-4]
        for m in re.finditer(r'[{,]\s*([A-Za-z0-9_]+)_\d{4}\s*=', txt):
            prefix_groups.setdefault(m.group(1), set()).add(g)

    # 只跟"明确的实体引用字段"，不要把模板正文里所有字符串都当模板名展开
    # （否则 portrait/平衡表里的名字会带出错组，白加载几十 MB）
    REF_FIELDS = (
        r'\.bullet\s*=\s*"([^"]+)"',
        r'create_entity\(\s*"([^"]+)"',
        r'spawner\.entity\s*=\s*"([^"]+)"',
        r'\.payload\s*=\s*"([^"]+)"',
        r'death_spawns\.(?:name|entity)\s*=\s*"([^"]+)"',
        r'\.sub_entity\s*=\s*"([^"]+)"',
        r'\.(?:entity|entity_name)\s*=\s*"([^"]+)"',
    )

    def prefixes_of(name, depth=1):
        """模板 name 需要的帧前缀；depth 控制引用展开层数。"""
        b = tmpl.get(name)
        if b is None:
            return set()
        # 有 <模板>_idle/attack/death 这类动画条目时，帧前缀以动画条目里的 prefix 为准；
        # sprites[i].prefix 那只是"动画命名空间"（如 enemy_darter），图集里并不存在这个名字。
        anim_pref = prefix_by_tmpl.get(name)
        if anim_pref:
            pfx = set(anim_pref)
        else:
            pfx = set(re.findall(r'render\.sprites\[\d+\]\.prefix\s*=\s*"([^"]+)"', b))
        for n in re.findall(r'render\.sprites\[\d+\]\.name\s*=\s*"([^"]+)"', b):
            if n in prefix_groups:
                pfx.add(n.rsplit("_", 1)[0] if re.search(r'_\d{4}$', n) else n)
        if depth > 0:
            for pat in REF_FIELDS:
                for other in set(re.findall(pat, b)):
                    if other != name and other in tmpl:
                        pfx |= prefixes_of(other, depth - 1)
        return pfx

    need = set()
    print("\n%-32s %-46s %s" % ("creep", "frame prefixes", "atlas groups"))
    for c in creeps:
        pfx = prefixes_of(c)
        gs = set()
        empty = []
        for p in pfx:
            hit = prefix_groups.get(p)
            if not hit:
                empty.append(p)
            gs |= hit or set()
        need |= gs
        print("%-32s %-46s %s" % (c, ",".join(sorted(pfx)) or "<none>", ",".join(sorted(gs)) or "<none>"))
        if empty:
            print("    └ 无对应图集组: %s" % ",".join(sorted(empty)))

    print("\n>>> 写入 data/levels/<L>_data.lua 的 required_textures:")
    for g in sorted(need - always):
        print('    "%s",' % g)
    print("\n常驻已覆盖（无需登记）: %s" % ",".join(sorted(need & always)))
    print("全部涉及组: %s" % ",".join(sorted(need)))

    print("""
提醒:
  * 上面只覆盖"敌人本体/子弹"的帧。敌人脚本里 E:create_entity 出来的粒子（如鳄鱼涉水的
    ps_enemy_crocs_water_bubbles_* → fx_water_bubble*）与它们用到的音效不在本表内，
    用 audit_level_resources.py 一起查。
  * "无对应图集组"的名字里，以 Def 结尾的多半是 exo 骨骼（Tank_crocs_animationsDef、
    hydra_unitDef、Fx_Shaman_BlocktowerDef...）→ 登记到 required_exoskeletons，不是贴图组。
  * 若一个普通帧前缀在所有 go_*.lua 里都找不到 → 运行时必然 "Sprite ... was not found"，
    说明这个单位在当前版本资源里根本没有贴图。
""")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
