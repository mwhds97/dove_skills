#!/usr/bin/env python3
"""校验 KR Dove 版关卡 <level>_paths.lua 的 connections 汇入点是否可达。

用法:  python check_path_connections.py <paths.lua> [更多 paths.lua ...]

对 connections[from] = to 的每条子路径：取 from 组该子路径的最后一个节点，
在 to 组的【同名子路径】里找最近节点，距离必须 <= PATH_POINTS_DISTANCE * 4 (=28px)，
否则引擎会回退成 ni = 1（目标组起点），表现为怪跑到地图另一头。
"""
import math
import re
import sys

THRESHOLD = 7 * 4  # all/constants.lua: PATH_POINTS_DISTANCE = 7


def strip_comments(src):
    out, i, n = [], 0, len(src)
    while i < n:
        if src.startswith("--[[", i):
            j = src.find("]]", i + 4)
            i = n if j < 0 else j + 2
        elif src.startswith("--", i):
            j = src.find("\n", i)
            i = n if j < 0 else j
        elif src[i] in "\"'":
            q, j = src[i], i + 1
            while j < n and src[j] != q:
                j += 2 if src[j] == "\\" else 1
            out.append(src[i:j + 1])
            i = j + 1
        else:
            out.append(src[i])
            i += 1
    return "".join(out)


def balance(src):
    stack, pairs = [], {")": "(", "]": "[", "}": "{"}
    for ch in strip_comments(src):
        if ch in "([{":
            stack.append(ch)
        elif ch in ")]}":
            if not stack or stack.pop() != pairs[ch]:
                return False, "unbalanced " + ch
    return (not stack), ("leftover " + "".join(stack) if stack else "ok")


def parse(body):
    """返回 (paths{pi:{spi:[(x,y)]}}, connections{from:to})"""
    key = body.index("paths = {")
    start = body.index("{", key)
    depth, i = 0, start
    while i < len(body):
        if body[i] == "{":
            depth += 1
        elif body[i] == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    block = body[start:i + 1]

    subs, depth, buf = [], 0, ""
    for ch in block:
        if ch == "{":
            depth += 1
            if depth == 3:
                buf = ""
            continue
        if ch == "}":
            if depth == 3:
                pts = [(float(a), float(b))
                       for a, b in re.findall(r"v\(\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\)", buf)]
                if pts:
                    subs.append(pts)
            depth -= 1
            continue
        if depth == 3:
            buf += ch

    per_group = 3  # 关卡编辑器固定为每组 3 条子路径
    paths = {gi // per_group + 1: {si + 1: subs[gi + si] for si in range(per_group)}
             for gi in range(0, len(subs), per_group)}

    conns = {}
    m = re.search(r"connections\s*=\s*\{(.*?)\}", body, re.S)
    if m:
        for a, b in re.findall(r"\[\s*(\d+)\s*\]\s*=\s*(\d+)", m.group(1)):
            conns[int(a)] = int(b)
    return paths, conns


def check(path):
    try:
        raw = open(path, encoding="utf-8").read()
    except OSError as e:
        print("=" * 70)
        print(path + "\n  读取失败: %s" % e)
        return 1
    src = raw[1:] if raw.startswith("\ufeff") else raw
    if "paths = {" not in src:
        print("=" * 70)
        print(path + "\n  找不到顶层 paths 表，可能不是 <level>_paths.lua")
        return 1
    ok, msg = balance(src)
    paths, conns = parse(src)
    print("=" * 70)
    print(path)
    print("  括号平衡:", "OK" if ok else "FAIL " + msg,
          "| 各组子路径数:", {pi: len(v) for pi, v in paths.items()},
          "| connections =", conns)
    bad = 0
    if not conns:
        print("  (无 connections，所有路径都在终点扣命)")
    for frm, to in sorted(conns.items()):
        if frm not in paths or to not in paths:
            print(f"  !! [{frm}]={to} 引用了不存在的路径组"); bad += 1; continue
        for spi in sorted(paths[frm]):
            if spi not in paths[to]:
                print(f"  !! [{frm}]={to} 子路径 {spi} 在目标组不存在"); bad += 1; continue
            last = paths[frm][spi][-1]
            dn, nd = min((math.hypot(last[0] - n[0], last[1] - n[1]), n)
                         for n in paths[to][spi])
            hit = dn <= THRESHOLD
            bad += 0 if hit else 1
            print("  [%d]=%d 子%2d 终点(%7.1f,%7.1f) -> 最近节点(%7.1f,%7.1f)  %7.1fpx  %s"
                  % (frm, to, spi, last[0], last[1], nd[0], nd[1], dn,
                     "命中" if hit else "超限 -> 回退起点 ni=1（错误）"))
        # 反向索引是否一对一
    rev = {}
    for a, b in conns.items():
        rev.setdefault(b, []).append(a)
    for b, srcs in rev.items():
        if len(srcs) > 1:
            print(f"  !! 多条来源汇入 [{b}] = {srcs}，path_connections_reverse 只保留一条")
    return bad


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    total = sum(check(a) for a in args)
    print("\n%s 共 %d 处问题" % ("全部通过" if total == 0 else "发现问题", total))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
