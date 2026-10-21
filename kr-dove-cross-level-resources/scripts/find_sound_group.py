#!/usr/bin/env python3
"""
find_sound_group.py -- 音效 ID -> 声音组 反查（Kingdom Rush Dove / KR1 重制版）

用途：插件（英雄/塔，全关卡通用）在技能里 S:queue("某音效") 时，该音效归属的
      声音组可能没随当前关卡加载 -> `sound_db.error play() - SOUND X defined but
      sound sources missing`。本脚本给出每个音效 ID 应该注入哪些声音组。

原理：
  _assets/<target>/sounds/sounds.lua  = 音效 ID -> files(ogg 文件名)
  _assets/<target>/sounds/groups.lua  = 声音组 -> files(ogg 文件名)   （493 个）
  => 用 ogg 文件名做桥：ID 的 files 与组的 files 有交集，即该组能提供音源。

⚠ 声音组在 groups.lua（不是 sounds.lua）；sounds.lua 里的 source_group="SFX"/"SPECIALS"
  是 openal 源池分类，与"组"无关，别混淆。

用法：
  python find_sound_group.py <KingdomRushDove 根> TerrainWukongMeteoriteCast Stage22AbominorAcidHit
  python find_sound_group.py <KingdomRushDove 根> --plugin <插件目录>      # 自动扫源码里的音效字面量
可选： --target <目录名>   默认 kr1-desktop
"""
import os
import re
import sys

IDENT_EQ = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*$")


def read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def top_entries(s):
    """切出 `return { ... }` 的一级条目 -> list[(key, body)]。用花括号配对，别用非贪婪正则。"""
    m = re.search(r"\breturn\b", s)
    if not m:
        return []
    start = s.find("{", m.end())
    if start < 0:
        return []
    out = []
    depth = 0
    entry_start = None
    for i in range(start, len(s)):
        ch = s[i]
        if ch == "{":
            depth += 1
            if depth == 2:
                entry_start = i
        elif ch == "}":
            if depth == 2 and entry_start is not None:
                pre = s[max(0, entry_start - 120):entry_start]
                km = IDENT_EQ.search(pre)
                out.append((km.group(1) if km else "?", s[entry_start:i + 1]))
                entry_start = None
            depth -= 1
            if depth == 0:
                break
    return out


QSTR = re.compile(r'"([^"]+)"')


def files_of(body):
    m = re.search(r"\bfiles\s*=\s*\{([^}]*)\}", body)
    if not m:
        return []
    return QSTR.findall(m.group(1))


def basenames(lst):
    return {os.path.basename(x) for x in lst}


LITERAL = re.compile(
    r'S:(?:queue|play)\s*\(\s*"([^"]+)"'      # S:queue("X") / S:play("X")
    r'|\.sound\s*=\s*"([^"]+)"'               # tt.melee.attacks[1].sound = "X"
    r'|sounds\s*=\s*\{\s*"([^"]+)"'           # sounds = {"X", ...}
)


def scan_plugin_literals(root):
    """从插件源码里抠出可疑的音效字面量（跳过注释行）。"""
    found = []
    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            if not fn.endswith(".lua"):
                continue
            p = os.path.join(dirpath, fn)
            for i, line in enumerate(read(p).splitlines(), 1):
                if line.lstrip().startswith("--"):
                    continue
                for mm in LITERAL.finditer(line):
                    sid = next(g for g in mm.groups() if g)
                    found.append((os.path.relpath(p, root), i, sid))
    return found


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__)
        return 2

    root = args[0]
    target = "kr1-desktop"
    rest = args[1:]
    if "--target" in rest:
        i = rest.index("--target")
        target = rest[i + 1]
        del rest[i:i + 2]

    sdir = os.path.join(root, "_assets", target, "sounds")
    spath = os.path.join(sdir, "sounds.lua")
    gpath = os.path.join(sdir, "groups.lua")
    for p in (spath, gpath):
        if not os.path.isfile(p):
            print("找不到 %s" % p)
            return 2

    sounds = {k: files_of(b) for k, b in top_entries(read(spath))}
    groups = {k: basenames(files_of(b)) for k, b in top_entries(read(gpath))}

    # ogg -> 组 反查表
    by_file = {}
    for g, fs in groups.items():
        for f in fs:
            by_file.setdefault(f, []).append(g)

    queries = []
    if "--plugin" in rest:
        i = rest.index("--plugin")
        pd = rest[i + 1]
        del rest[i:i + 2]
        print("== 扫描插件源码：%s" % pd)
        hits = scan_plugin_literals(pd)
        seen = set()
        for rel, ln, sid in hits:
            if sid in seen:
                continue
            seen.add(sid)
            queries.append(sid)
            print("  %s:%d  %s" % (rel, ln, sid))
        print()

    queries += [a for a in rest if not a.startswith("--")]

    if not queries:
        print("没有待查音效；直接给音效 ID 或用 --plugin <目录>")
        return 2

    all_groups = set()
    print("== 音效 -> 声音组 ==")
    for sid in queries:
        fl = sounds.get(sid)
        if fl is None:
            print("  %-40s ⚠ 未在 sounds.lua 定义" % sid)
            continue
        cands = []
        for f in basenames(fl):
            for g in by_file.get(f, []):
                if g not in cands:
                    cands.append(g)
        if cands:
            all_groups.update(cands)
            print("  %-40s -> %s" % (sid, ", ".join(sorted(cands))))
        else:
            print("  %-40s ⚠ 无任何组包含 %s" % (sid, basenames(fl)))

    if all_groups:
        print()
        print("== 建议注入的声音组（REQUIRED_SOUND_GROUPS）==")
        print("    {" + ", ".join('"%s"' % g for g in sorted(all_groups)) + "}")
        print("  ⚠ 多个组含同一 ogg 时取最小的那个即可（可 ls -la 对比 dds/ogg 体积）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
