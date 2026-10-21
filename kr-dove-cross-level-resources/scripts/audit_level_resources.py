# -*- coding: utf-8 -*-
"""核查自建关卡"敌人脚本里动态创建的特效/粒子"与"敌人音效"是否缺组。

用法:
  python audit_level_resources.py <KingdomRushDove 根> <该关 _waves_campaign.lua> [<该关 _data.lua>]

为什么要单独查这两类:
  * find_level_atlases.py 只看敌人本体/子弹的帧。鳄鱼系敌人在 scripts.enemy_crocs_basic.insert
    里 E:create_entity("ps_enemy_crocs_water_bubbles_"..size_names[unit.size]) 动态造粒子，
    这些粒子的帧（fx_water_bubble*、fx_water_splash*）只存在于关卡图集（go_stage121/122），
    缺了就会刷屏 `image_db.error s() - Sprite fx_water_bubble_big_projectile_00XX was not found`。
  * 音效同理: `sound_db.error play() - SOUND XXX defined but sound sources missing`
    = 该声音的 ogg 不在任何已加载的音效组里，必须把该组写进 required_sounds。
    注意 common 组里没有 EnemyRazingRhinoDeath / RTWaterExplosion，别想当然。

坑:
  * 解析 groups.lua 必须用花括号配对，别用非贪婪正则 `([A-Za-z0-9_]+)=\\{files=\\{(.*?)\\}\\}`
    —— 会跨组误判（曾把 stage_22 的文件误报成在 common 里），从而漏掉真正要补的组。
  * 搜文件名要用完整文件名匹配，不能用子串（razingRhino 会命中 basicAttack/charge，
    于是以为 common 里已经有 death 音，实际没有）。
"""
import os, re, sys, io, glob, collections


def read(p):
    with io.open(p, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def brace_body(text, start):
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


def key_blocks(text, key):
    """所有顶层 `key = {...}` 的内容（用 (?<![A-Za-z_]) 避免匹配 plugin_required_xxx）。"""
    return [brace_body(text, m.end() - 1)
            for m in re.finditer(r'(?<![A-Za-z_])' + re.escape(key) + r'\s*=\s*\{', text)]


def register_blocks(text):
    ms = [(m.start(), m.group(1)) for m in
          re.finditer(r'(?:E:register_t|RT)\(\s*"([^"]+)"', text)]
    out = {}
    for i, (st, nm) in enumerate(ms):
        e = ms[i + 1][0] if i + 1 < len(ms) else len(text)
        out.setdefault(nm, text[st:e])
    return out


def script_blocks(text):
    """{scripts.名字: 正文}，正文到下一个 \nscripts.X = { 为止。"""
    ms = [(m.start(), m.group(1)) for m in
          re.finditer(r'\nscripts\.([A-Za-z0-9_]+)\s*=\s*\{', text)]
    out = {}
    for i, (st, nm) in enumerate(ms):
        e = ms[i + 1][0] if i + 1 < len(ms) else len(text)
        out.setdefault(nm, text[st:e])
    return out


def main(root, waves_path, level_data=None):
    creeps = sorted(set(re.findall(r'creep\s*=\s*"([^"]+)"', read(waves_path))))
    print("distinct creeps: %d" % len(creeps))

    # ---- 已加载组 ----
    game_lua = read(os.path.join(root, "all", "game.lua"))
    loaded_snd = set(re.findall(r'"([^"]+)"', key_blocks(game_lua, "game.required_sounds")[0]))
    loaded_tex = set(re.findall(r'"([^"]+)"', key_blocks(game_lua, "game.required_textures")[0]))
    if level_data and os.path.exists(level_data):
        ld = read(level_data)
        for b in key_blocks(ld, "required_sounds") + key_blocks(ld, "plugin_required_sounds"):
            loaded_snd |= set(re.findall(r'"([^"]+)"', b))
        for b in key_blocks(ld, "required_textures") + key_blocks(ld, "plugin_required_textures"):
            loaded_tex |= set(re.findall(r'"([^"]+)"', b))

    # ---- 音效库 ----
    sdir = os.path.join(root, r"_assets\kr1-desktop\sounds")
    stext = read(os.path.join(sdir, "sounds.lua"))
    sounds = {}
    for m in re.finditer(r'[,{]([A-Za-z0-9_]+)=\{\s*files\s*=\s*\{', stext):
        sounds[m.group(1)] = re.findall(r'"([^"]+)"', brace_body(stext, m.end() - 1))
    gtext = read(os.path.join(sdir, "groups.lua"))
    groups = {}
    for m in re.finditer(r'[,{]([A-Za-z0-9_]+)\s*=\s*\{', gtext):
        b = brace_body(gtext, m.end() - 1)
        fs = re.search(r'files\s*=\s*\{', b)
        g = set(re.findall(r'"([^"]+)"', brace_body(b, fs.end() - 1))) if fs else set()
        ss = re.search(r'sounds\s*=\s*\{', b)
        if ss:
            for sid in re.findall(r'"([^"]+)"', brace_body(b, ss.end() - 1)):
                g |= set(sounds.get(sid, []))
        groups[m.group(1)] = g
    file2group = collections.defaultdict(set)
    for g, fs in groups.items():
        for f in fs:
            file2group[f].add(g)

    # ---- 模板 / 脚本 ----
    tmpl = {}
    for rel in (r"kr1\enemies.lua", r"kr1\boss.lua", r"kr1\game_templates.lua", r"all\templates.lua"):
        p = os.path.join(root, rel)
        if os.path.exists(p):
            tmpl.update(register_blocks(read(p)))
    scripts = {}
    for rel in (r"kr1\game_scripts.lua", r"all\scripts.lua", r"kr1\hero_scripts.lua"):
        p = os.path.join(root, rel)
        if os.path.exists(p):
            for k, v in script_blocks(read(p)).items():
                scripts.setdefault(k, v)

    # ---- 图集索引（一次读盘）----
    fullhd = os.path.join(root, r"_assets\kr1-desktop\images\fullhd")
    tex = {}
    for f in glob.glob(os.path.join(fullhd, "go_*.lua")):
        tex[os.path.basename(f)[:-4]] = set(re.findall(r'[,{]([A-Za-z0-9_]+)=\{a_name=', read(f)))

    def groups_of_prefix(p):
        gs = set(g for g, names in tex.items() if (p + "_0001") in names)
        if not gs:
            gs = set(g for g, names in tex.items() if any(x.startswith(p + "_") for x in names))
        return gs

    miss_snd = collections.defaultdict(set)      # 组 -> {"creep(soundID)"}
    miss_tex = collections.defaultdict(set)      # 前缀 -> {"模板/来源"}
    dynamic = set()
    for c in creeps:
        b = tmpl.get(c)
        if b is None:
            print("!! 模板未找到: %s" % c)
            continue
        # 音效
        for sid in set(re.findall(r'sound_events\.[A-Za-z0-9_]+\s*=\s*"([^"]+)"', b)):
            files = sounds.get(sid)
            if not files:
                miss_snd["<音效未定义>"].add("%s(%s)" % (c, sid))
                continue
            for f in files:
                gs = file2group.get(f, set())
                if not (gs & loaded_snd):
                    for g in gs or {"<该文件不属于任何组>"}:
                        miss_snd[g].add("%s(%s)" % (c, sid))
        # 脚本里创建的特效
        srefs = set(re.findall(r'create_entity\(\s*"([^"]+)"', b))
        for sn in set(re.findall(r'scripts\.([A-Za-z0-9_]+)\.', b)):
            blk = scripts.get(sn)
            if not blk:
                continue
            srefs |= set(re.findall(r'create_entity\(\s*"([^"]+)"', blk))
            for lit in re.findall(r'create_entity\(\s*"([^"]+)"\s*\.\.', blk):
                dynamic.add((c, sn, lit))
        for r in srefs:
            tb = tmpl.get(r)
            if tb is None:
                continue
            names = set(re.findall(r'particle_system\.name\s*=\s*"([^"]+)"', tb))
            names |= set(re.findall(r'render\.sprites\[\d+\]\.prefix\s*=\s*"([^"]+)"', tb))
            for n in names:
                gs = groups_of_prefix(n)
                if not (gs & loaded_tex):
                    miss_tex[n].add("%s(经 %s)" % (c, r))

    print("\n=== 音效: 需要补进 required_sounds 的组 ===")
    if not miss_snd:
        print("  （无）")
    for g, who in sorted(miss_snd.items()):
        print("  %-28s n=%-3d 例: %s" % (g, len(who), sorted(who)[:4]))
    print("\n=== 贴图: 需要补进 required_textures 的帧前缀 ===")
    if not miss_tex:
        print("  （无）")
    for n, who in sorted(miss_tex.items()):
        print("  %-40s 组=%s 例: %s" % (n, sorted(groups_of_prefix(n)) or "无", sorted(who)[:3]))
    if dynamic:
        print("\n=== ⚠ 动态拼名的实体（静态扫描抓不全，要人工确认）===")
        for d in sorted(dynamic):
            print("  %s 经 scripts.%s 创建 \"%s\"..变量  → 把该系列模板逐个查一遍" % d)
    print("\n提示: 同一批帧可能同时存在于多个组（例如 go_stage121 与 go_stage122 的 fx_water_* "
          "62 帧美术完全相同，121 只有 1 张 8MB dds、122 是 2 张 32MB）——优先登记体积小的组。")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
