#!/usr/bin/env python3
"""验证 Dove 插件「游戏内可改配置」是否真的生效。

用法：
    python verify_config_mapping.py <插件目录> [--balance scripts/balance.lua]
                                   [--config <entry>_config.lua] [--module <entry>]

插件目录示例：KingdomRushDove/mods/local/johnny_deadeye
<entry> 默认取插件目录名；配置模块名默认 "<entry>.<entry>_config"。

检查项：
  1. 面板侧静态约束：key_order_list ↔ 数据键 ↔ key_label_map 一一对应；数组长度足够。
  2. 无配置时 B 必须是纯默认值（可加 --expect 抽查，默认只做内部自洽检查）。
  3. 逐键哨兵映射：一次只把一个键设为唯一哨兵值 → 报告它改动了 B 的哪些路径。
  4. 死旋钮：任何键改了 B 却毫无变化的，直接列出。
  5. B.reload_config 连续调用后仍存活（抓「原地 refill 把函数一起清掉」的坑）。

依赖：lupa（`pip install lupa --index-url https://pypi.org/simple`）。
⚠ 中文路径下 Lua 的 dofile/io.open 会报 Illegal byte sequence，
  所以这里一律用 Python 读源码，再交给 Lua 的 load()。
"""
import argparse
import os
import sys

try:
    from lupa import LuaRuntime
except ImportError:
    sys.exit("需要 lupa：pip install lupa --index-url https://pypi.org/simple")

META_KEYS = {"key_order_list", "key_label_map", "__default_config"}


def load_lua_table(L, path):
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    L.globals()._SRC = src
    name = os.path.basename(path)
    chunk = L.eval(
        '(function() local f, e = load(_SRC, "@%s"); if not f then error(e) end; return f end)()'
        % name
    )
    return chunk()


def lua_vals(t):
    return list(t.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plugin_dir")
    ap.add_argument("--balance", default="scripts/balance.lua")
    ap.add_argument("--config", default=None)
    ap.add_argument("--module", default=None)
    args = ap.parse_args()

    plugin_dir = args.plugin_dir.rstrip("/\\")
    entry = os.path.basename(plugin_dir)
    config_path = os.path.join(plugin_dir, args.config or f"{entry}_config.lua")
    balance_path = os.path.join(plugin_dir, args.balance)
    module = args.module or f"{entry}.{entry}_config"

    for p in (config_path, balance_path):
        if not os.path.isfile(p):
            sys.exit(f"文件不存在: {p}")

    L = LuaRuntime(unpack_returned_tuples=True)
    cfg = load_lua_table(L, config_path)

    # ---------- 1) 面板侧静态约束 ----------
    data = {str(k): v for k, v in cfg.items() if str(k) not in META_KEYS}
    order = [str(x) for x in lua_vals(cfg["key_order_list"])] if cfg["key_order_list"] else []
    labels = ({str(k): str(v) for k, v in cfg["key_label_map"].items()}
              if cfg["key_label_map"] else {})
    arrays = {k: lua_vals(v) for k, v in data.items()
              if v is not None and hasattr(v, "values")}

    errs = []
    for k in order:
        if k not in data:
            errs.append(f"key_order_list 里的 {k} 在配置中不存在（面板会静默跳过）")
        if k not in labels:
            errs.append(f"{k} 缺 key_label_map 标签（面板会静默跳过）")
    for k in data:
        if order and k not in order:
            errs.append(f"配置键 {k} 不在 key_order_list（面板永远不显示）")
    for k in labels:
        if k not in data:
            errs.append(f"key_label_map 的 {k} 在配置中不存在")

    # 数组长度：balance.nums 的 min_len 由调用方决定，这里只报"有没有明显短板"
    for k, vals in arrays.items():
        if not vals:
            errs.append(f"数组 {k} 为空")
            continue
        for i, x in enumerate(vals, 1):
            if isinstance(x, bool) or not isinstance(x, (int, float)):
                errs.append(f"{k}[{i}] 非数字：{x!r}（面板只支持全数字数组）")

    print(f"插件：{entry}")
    print(f"配置数据键 {len(data)} | key_order_list {len(order)} | 标签 {len(labels)} "
          f"| 数组 {len(arrays)}")
    print("\n== 面板侧静态检查 ==")
    if errs:
        for e in errs:
            print(" ✗", e)
    else:
        print(" ✓ 全部通过")

    # ---------- 2~5) 跑真 Lua ----------
    with open(balance_path, "r", encoding="utf-8") as f:
        L.globals().BAL_SRC = f.read()

    L.execute("""
CONFIG = nil
package.preload["__MODULE__"] = function() return CONFIG end
local chunk, err = load(BAL_SRC, "@balance.lua")
if not chunk then error("balance 编译失败: " .. tostring(err)) end
B = chunk()

function set_config(t) CONFIG = t end

function collect_scalars(t, prefix, out)
	for k, v in pairs(t) do
		local key
		if type(k) == "number" then key = prefix .. "[" .. k .. "]"
		elseif type(k) == "string" then key = prefix .. "." .. k
		else key = prefix .. ".<" .. tostring(k) .. ">" end
		if type(v) == "table" then collect_scalars(v, key, out)
		elseif type(v) == "number" or type(v) == "boolean" then out[key] = v end
	end
	return out
end

function snapshot() return collect_scalars(B, "B", {}) end
function reload_type() return type(B.reload_config) end
""".replace("__MODULE__", module))

    print("\n== 无配置时 ==")
    print("B.reload_config 类型:", L.eval("reload_type()"))
    base = dict(L.eval("snapshot()").items())
    print("B 中的标量(数字/布尔)字段数:", len(base))
    if not base:
        print(" ✗ B 里没有标量字段，balance 结构对不上，后面的映射检查无意义")
    if L.eval("reload_type()") != "function":
        print(" ✗ B.reload_config 不存在 —— 配置无法热刷新")

    def same(a, b):
        # 布尔与数字不可互比：True == 1 在 Python 里成立，会互相冒充
        if isinstance(a, bool) != isinstance(b, bool):
            return False
        return a == b

    print("\n== 逐键哨兵映射 ==")
    dead, report = [], []
    for i, (key, v) in enumerate(sorted(data.items())):
        # 布尔键必须写布尔哨兵：balance 里的 bool() 只认 boolean，
        # 写数字会被判类型不符 → 回退默认值 → 假死旋钮（曾经的误报来源）。
        is_bool_key = isinstance(v, bool)
        sentinel = (not v) if is_bool_key else (700000 + i)
        tbl = L.table()
        if key in arrays:
            arr = L.table()
            # 长度取原数组长度，但对只有几项的数组给足 10 项，避免被 min_len 挡掉
            n = max(len(arrays[key]), 10)
            for j in range(1, n + 1):
                arr[j] = 700000 + i
            tbl[key] = arr
        else:
            tbl[key] = sentinel
        L.globals().set_config(tbl)
        L.execute("B.reload_config(CONFIG)")
        snap = dict(L.eval("snapshot()").items())
        # 与「无配置基线」比：比哨兵值比更稳（不会把别的同值字段算成命中）
        changed = sorted(k for k, val in snap.items() if k not in base or not same(val, base[k]))
        if not changed:
            dead.append(key)
            report.append((key, "!! 无任何字段变化（死旋钮）"))
        else:
            shown = ", ".join(changed[:4])
            if len(changed) > 4:
                shown += f" …（共 {len(changed)} 项）"
            report.append((key, shown))

    for key, info in report:
        print(f' {"✗" if info.startswith("!!") else " "} {key:38s} -> {info}')

    print("\n== 结论 ==")
    print("死旋钮:", len(dead), dead if dead else "（无）")
    print("多次 reload 后 B.reload_config 类型:", L.eval("reload_type()"))
    ok = not errs and not dead and L.eval("reload_type()") == "function"
    print("总判定:", "通过" if ok else "有问题的项见上")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
