#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把本目录的 Dove 技能副本与技能库同步（覆盖式刷新），并刷新项目级长期约定快照。

用法：
    python sync_skills.py                # 源 -> 本目录，覆盖式刷新
    python sync_skills.py --dry-run      # 只列差异，不动任何文件
    python sync_skills.py --src <目录>   # 指定技能库（默认 %USERPROFILE%\\.workbuddy\\skills）
    python sync_skills.py --only kr-dove-ui-panel [--only ...]
    python sync_skills.py --skip-memory  # 只刷技能，不动 memory/ 下的约定快照
    python sync_skills.py --project <Dove工程根>   # 指定工程根（默认从本文件位置推导）

行为：
  · 只处理下面 SKILLS 白名单里的 15 个技能，其他技能（Vue/Compose 等）不碰
  · 对白名单内的技能做「先删后拷」⇒ 源里删掉的附件在这里也会消失，不会留残骸
  · 绝不删除本目录下的 README.md、sync_skills.py 或任何非白名单内容
  · 源目录不存在的技能跳过并告警（不删本地副本，防止误清空）
  · memory/ 下项目级约定按字节比对后覆盖，memory/README.md 不参与同步
"""
import argparse
import filecmp
import os
import shutil
import sys

SKILLS = [
    "kr-dove-enemy-data",
    "kr-dove-tech-tree-data",
    "kr-remaster-bytecode-decompile",
    "kr-dove-tower-port",
    "kr-dove-kr6-powers-port",
    "kr-dove-ui-panel",
    "iron-marines-hero-port",
    "kr-dove-stage-hero-port",
    "kr-dove-tavern-add-unit",
    "kr-dove-mobile-tower",
    "kr-dove-level-waves",
    "kr-dove-cross-level-resources",
    "kr-dove-bullet-aoe-fx",
    "kr-dove-plugin-config",
    "kr-dove-offline-lua-harness",
]


IGNORE_DIRS = {"__pycache__", ".pytest_cache", ".ipynb_checkpoints"}
IGNORE_PAT = ("__pycache__", "*.pyc", ".pytest_cache")

MEMORY_SUBDIR = "memory"


def find_project_root(start):
    """从 start 向上找含 KingdomRushDove 的目录，即 Dove 工程根。找不到返回空串。"""
    p = os.path.dirname(os.path.abspath(start))
    for _ in range(12):
        if os.path.isdir(os.path.join(p, "KingdomRushDove")):
            return p
        parent = os.path.dirname(p)
        if parent == p:
            break
        p = parent
    return ""


def memory_sources(project):
    """返回 [(源文件, 副本内文件名)]。只同步项目级约定，日志与用户级约定不参与。"""
    if not project:
        return []
    return [(os.path.join(project, ".workbuddy", "memory", "MEMORY.md"),
             "项目级长期约定.md")]


def sync_memory(project, dst, dry_run):
    """刷新 memory/ 下两份长期约定。返回 (更新数, 跳过数, 总字符数)。"""
    outdir = os.path.join(dst, MEMORY_SUBDIR)
    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    changed = skipped = 0
    total_chars = 0
    print("\n长期约定：")
    for src, name in memory_sources(project):
        if not os.path.isfile(src):
            print("[skip] 源里没有 %s（%s）" % (name, src))
            skipped += 1
            continue
        out = os.path.join(outdir, name)
        same = os.path.isfile(out) and filecmp.cmp(src, out, shallow=False)
        if same:
            print("[same] %s" % name)
            continue
        state = "更新" if os.path.isfile(out) else "新增"
        if dry_run:
            print("[diff] %-24s %s" % (name, state))
        else:
            shutil.copyfile(src, out)
            print("[sync] %-24s %s" % (name, state))
        changed += 1
    for src, name in memory_sources(project):
        p = src if os.path.isfile(src) else os.path.join(outdir, name)
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as fh:
                total_chars += len(fh.read())
    return changed, skipped, total_chars


def diff_tree(a, b):
    """返回 (仅源有, 仅副本有, 内容不同) 三组相对路径。"""
    only_src, only_dst, differ = [], [], []
    if not os.path.isdir(b):
        return None, None, None

    def walk(rel):
        da = os.path.join(a, rel) if rel else a
        db = os.path.join(b, rel) if rel else b
        try:
            names_a = set(os.listdir(da)) - IGNORE_DIRS
        except OSError:
            names_a = set()
        try:
            names_b = set(os.listdir(db)) - IGNORE_DIRS
        except OSError:
            names_b = set()
        for n in names_a - names_b:
            only_src.append(os.path.join(rel, n) if rel else n)
        for n in names_b - names_a:
            only_dst.append(os.path.join(rel, n) if rel else n)
        for n in names_a & names_b:
            pa = os.path.join(da, n)
            pb = os.path.join(db, n)
            r = os.path.join(rel, n) if rel else n
            if os.path.isdir(pa) and os.path.isdir(pb):
                walk(r)
            elif os.path.isfile(pa) and os.path.isfile(pb):
                if not filecmp.cmp(pa, pb, shallow=False):
                    differ.append(r)
            else:
                differ.append(r)

    walk("")
    return only_src, only_dst, differ


def count_files(root):
    n = size = 0
    for dirpath, _, files in os.walk(root):
        for f in files:
            n += 1
            try:
                size += os.path.getsize(os.path.join(dirpath, f))
            except OSError:
                pass
    return n, size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(os.path.expanduser("~"), ".workbuddy", "skills"))
    ap.add_argument("--dst", default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--only", action="append", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--project", default=None, help="Dove 工程根（默认从本文件位置推导）")
    ap.add_argument("--skip-memory", action="store_true", help="不刷新 memory/ 下的长期约定")
    args = ap.parse_args()

    src = os.path.abspath(args.src)
    dst = os.path.abspath(args.dst)
    if not os.path.isdir(src):
        sys.exit("源目录不存在：%s" % src)
    if os.path.dirname(dst) == dst:
        sys.exit("拒绝在盘符根目录操作：%s" % dst)

    targets = [s for s in SKILLS if (not args.only or s in args.only)]
    unknown = [s for s in (args.only or []) if s not in SKILLS]
    for s in unknown:
        print("[warn] --only 里有不在白名单的技能，已忽略：%s" % s)

    print("源：%s" % src)
    print("目标：%s" % dst)
    print("技能：%d 个%s\n" % (len(targets), "（dry-run）" if args.dry_run else ""))

    changed = skipped = 0
    for name in targets:
        a = os.path.join(src, name)
        b = os.path.join(dst, name)
        if not os.path.isdir(a):
            print("[skip] 源里没有 %s（保留本地副本）" % name)
            skipped += 1
            continue

        only_src, only_dst, differ = diff_tree(a, b)
        if only_src is None:
            state = "新增"
        elif only_src or only_dst or differ:
            state = "更新（+%d 源独有 / -%d 副本独有 / ~%d 不同）" % (
                len(only_src), len(only_dst), len(differ))
        else:
            print("[same] %s" % name)
            continue

        if args.dry_run:
            print("[diff] %-32s %s" % (name, state))
            for rel in (only_src or [])[:5]:
                print("         + %s" % rel)
            for rel in (only_dst or [])[:5]:
                print("         - %s" % rel)
            for rel in (differ or [])[:8]:
                print("         ~ %s" % rel)
            changed += 1
            continue

        if os.path.isdir(b):
            shutil.rmtree(b)
        shutil.copytree(a, b, ignore=shutil.ignore_patterns(*IGNORE_PAT))
        print("[sync] %-32s %s" % (name, state))
        changed += 1

    if not args.dry_run and changed:
        n, size = count_files(dst)
        print("\n完成：%d 个技能已刷新；本目录现有 %d 个文件 / %.1f KB" % (changed, n, size / 1024.0))
    elif not changed:
        print("\n无需更新：技能全部一致。")
    if skipped:
        print("跳过 %d 个（源里不存在）。" % skipped)

    if not args.skip_memory:
        project = os.path.abspath(args.project) if args.project else find_project_root(dst)
        if not project:
            print("\n[warn] 定位不到 Dove 工程根，跳过长期约定；可用 --project <路径> 指定。")
        else:
            m_changed, m_skip, m_chars = sync_memory(project, dst, args.dry_run)
            if m_changed:
                print("\n约定：%d 份已刷新%s（合计 %d 字符）"
                      % (m_changed, "（dry-run）" if args.dry_run else "", m_chars))
            else:
                print("\n约定：无需更新。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
