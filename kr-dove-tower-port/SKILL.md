---
name: kr-dove-tower-port
description: 王国保卫战Dove版插件塔移植/调试要点：FL写法陷阱（animation_start第5参数是loop）、找目标API签名核对（refind_foremost_enemy无store、注释不可信）、子弹伤害结算与 damage_hooks 条件加伤、塔菜单网格收纳（tower_menu_grid是工厂函数）、伤害公式（damage_inc×等级）、特技面板i18n键规则与描述随配置自动生成、AppData同步与语法校验流程。移植新塔或排查塔动画/伤害/文本/目标选择问题时使用。
agent_created: true
---

# KR Dove 版塔插件移植与调试

适用：把 FL7.5（KR联盟改版）的塔移植为 Dove 版独立插件，或排查塔的动画/伤害/文本问题。

## 硬性规则（踩过的坑）

1. **`U.animation_start(entity, name, flip_x, ts, loop, idx)` 第5参数是 loop**（all/utils.lua:372）。射击动画必须单次播放：
   - 启动：`U.animation_start_once_specific(this, an, af, ts, ssid)`
   - 射完等待：`U.y_animation_wait_specific(this, ssid)` 后用 `animation_start_once_specific` 切回 idle（`shot_animation` 返回对朝向 idle 名，参照 kr1/tower_scripts.lua `tower_archer`）
   - 循环待机：`U.animation_start_loop_specific`
   - **禁止 FL 的 `animation_start(..., 1, ssid)`**——真值 loop 会让射击动画无限循环且 ts/runs 不重置
2. **复用原版脚本函数前必查字段依赖**：如 `scripts.aura_arcane_burst.update` 依赖奥术塔专属 `this.sleep_chance`（nil 即崩）。非奥术塔要自写 update（FL 源逻辑 + Dove API）。
3. **子弹伤害结算**：`SU.create_bullet_damage`（all/script_utils.lua L571+）= `min/max + damage_inc × bullet.level`（level=技能等级，普攻传 0）；光环 = `level × damage_inc`。写技能描述按此逐级算。
4. **特技面板 i18n 键**：按 `{i18n_key}_{powers表键}_NAME/DESCRIPTION_{等级}` 动态查找（如 `TOWER_X_BURST_NAME_1`、`TOWER_X_SLUMBER_DESCRIPTION_2`）。键前缀必须与 powers 表键一致，自命名会显示原始键名。
5. **插件环境**：`queue_damage` 是各 scripts 文件的 local（手推 `store.damage_queue[#store.damage_queue+1]=d`）；`random`→`math.random`；`tpos`/`apply_precision` 需自己实现；发射必中用 `U.refind_foremost_enemy(enemy, flags, bans)` —— ⚠ **只有 3 个参数，别传 store**（FL 写法在这条上会崩，详见下文「找目标 API 的签名」一节）。
6. ⚠⚠ **require 引擎模块时，模块名必须与「引擎侧写的名字」完全一致，否则你拿到的是另一张表**（2026-09-30 实战踩坑，功能整体静默失效）：
   - 机制：`main.lua:110-169` 的 `search_roots` = `{"", "lib", "all", "all-<target>", "<game>", …}`，同一个文件常能由两个模块名命中；而 Lua 的 `require` 按**名字字符串**缓存 `package.loaded` → 同文件两个名字 = **执行两次 = 两张表**（已实证 `A == B → false`）。插件的钩子/注册挂在另一张表上，引擎永远看不见，**而且不报错**（那张表上函数同名，`hook_utils.HOOK` 检查通过）。
   - 判别：**别按"前缀规矩"猜，直接看引擎怎么写的**。实证对照：`image_db` → `lib.klove.image_db`（引擎 32 处 + 全部插件统一，共享实例）；`kui_db` → `klove.kui_db`（**无 `lib.` 前缀**，`all/director.lua:13`、`all-desktop/screen_map.lua:31` 等 5 处）；`vector` → `lib.klua.vector`（在 `lib/klua/`；`lib/klove/vector.lua` **不存在**）；`log` → `lib.klua.log`。
   - 次生坑：**`pcall(require, "<不存在的名>")` 只静默返回 false**。若代码后续写 `if not ok_x then return end`，整个功能变 no-op 且零日志 —— 排查"功能像没接上"时，先看这几个 `ok_*` 是不是 false。
   - 自检工具：`.workbuddy/probe_deadeye_module_names.py`（按模块短名比对"插件写法 vs 引擎主流写法"，含负向用例；把 PLUGIN 换成你的插件目录即可复用）。
7. ⭐⭐ **`hook_utils.HOOK` 不去重 —— 重复安装会叠加 handler**（2026-10-02 reinforcement_more_choice 踩到）：
   - `plugin/all/hook_utils.lua:96-97` 是**无条件 `table.insert`**，同一个 `(obj, fn_name, handler)` 装两次 = 链上挂两份。
   - 危险点：`plugin:reload` / `on_config_change` 里再调一次 `init()`（很多插件这么写）⇒ `E.Load` 钩子叠多层 ⇒ `register_base_template` 等被重复执行。
   - **修法**：把挂钩子单独抽成方法，**先 `UNHOOK` 再 `HOOK`**（`UNHOOK` 为同一函数引用删除所有匹配项并重建链，`hook_utils.lua:136-162`）：
     ```lua
     function plugin:hook_engine()
         hook_utils.UNHOOK(E, "Load", E_Load_hook)
         hook_utils.UNHOOK(UP, "patch_templates", UP_patch_templates)
         hook_utils.HOOK(E, "Load", E_Load_hook)
         hook_utils.HOOK(UP, "patch_templates", UP_patch_templates)
     end
     ```
   - ⚠ 注意 `HOOK` 链的**责任链语义**：预编译链里重复调用 `next` 会**再执行同一个后续 handler**（不是推进到下一环）⇒ handler 内 `next(...)` **必须恰好调用一次**。


## ⭐⭐ 找目标 API 的签名：注释会骗你，**永远信函数定义行**

同一批 `find_foremost_enemy*` API 签名各不相同，且 `---@param` 注释常从别的函数抄过来没删干净。
错传一个参数 → 后续位置参数整体错位 → 崩在 `all/seek.lua:46: bad argument #2 to 'band' (number expected, got table)`（拿 table 当掩码）。

**真实签名（2026-10 核对，`all/utils.lua`）**：

| 函数 | 签名 | 参 |
|---|---|---|
| `U.refind_foremost_enemy` | `(last_enemy, flags, bans)` | **3** —— **没有 store** |
| `U.find_foremost_enemy` | `(store, origin, min_range, max_range, prediction_time, flags, bans, filter_func, min_override_flags)` | 9（后两个可选） |
| `U.find_foremost_enemy_with_flying_preference` | `(store, origin, min_range, max_range, prediction_time, flags, bans, filter_func, min_override_flags)` | 9 |
| `U.find_foremost_enemy_with_max_coverage` | 同上 + `cover_range` | 10 |
| `seek.find_foremost_enemy_in_range_filter_off` | `(origin, range, prediction_time, flags, bans)` | 5（返回 3 值） |
| `seek.find_foremost_enemy_with_flying_preference_in_range_filter_off` | `(origin, range, flags, bans)` | **4** —— 少 `prediction_time` |

**最坑的一条**：`U.refind_foremost_enemy` **上方有 `---@param store table` 注释，但函数体只有 3 个形参**。
（`utils.lua:1481-1488`：注释残留了 `store`/`filter_func`/`min_override_flags`，是从 `find_foremost_enemy*` 系列复制来的。）
照注释写 `refind_foremost_enemy(enemy, store, flags, bans)` → `flags = store`(table)、`bans = flags`、
真正的 `bans` 被丢弃 → `enemy_filter_simple` 里 `band(e.vis.flags, bans)` 收 table 直接崩。

**判别手法**（照做，别靠猜）：
```bash
# 1. 直接看定义行，这是唯一事实
grep -rn "^function U\.\(find\|refind\)_foremost" all/utils.lua
grep -rn "^function seek\..*foremost" all/seek.lua
# 2. 判断某个参数是不是「死参数」：数它在函数体里出现的次数
#    只出现 1 次 = 只有签名里那一次 = 死参数
```
实证：`store` 在 `all/seek.lua` 出现 9 次，**全部是 `---@param store any` 注释**，正文零使用。
同一文件里注释与签名冲突时，**信签名**。

⚠ 迁移自 FL 的插件最容易在这条上翻车：FL 那套确实传 `store`，Dove 版不传。
一次性自查全工程：
```bash
grep -rn "refind_foremost_enemy(\|find_foremost_enemy(" mods/local --include=*.lua | grep -v "^.*--"
```
逐个对照上表数实参个数。

## ⭐⭐ 塔菜单网格收纳（本体 2026-10 起，插件**别再自己分页**）

本体已把这套接口改过三轮（places 9→24、表→函数、收纳白名单→黑名单），每次插件都崩在加载期。
现在是这个样子，照这个写，不要再自建分页：

**1. `data.tower_menu_grid` 是工厂函数，不是表**（`kr1-desktop/data/game_gui_data.lua`）

```lua
tower_menu_grid = function(ui_settings)
    local cols = math.max(1, math.floor(ui_settings.tower_menu_grid_cols))
    local rows = math.max(1, math.floor(ui_settings.tower_menu_grid_rows))
    ...  return {cols, rows, x_unit=56, y_unit=62, view_pos, view_size,
                 page_button_size=v(60,60), page_prev_pos, page_next_pos,
                 background_color={47,34,6,100}, background_radius=10, background_padding=6, ...}
end
```

行列数是**玩家可配**的：`patches/ui_settings_template.lua` 默认 `cols=7 / rows=4`，
玩家存档 `AppData/Roaming/LOVE/kingdom_rush_dove/ui_settings.lua` 里没有这两个字段，
靠 `Configer.get_all` 的 `merge_defaults` 补默认。**插件必须这么取**：

```lua
local ok, configer = pcall(require, "dove_modules.configer")
local grid = ggd.tower_menu_grid(ok and configer.ui_settings() or {tower_menu_grid_cols=7, tower_menu_grid_rows=4})
```

⚠ 写成 `local grid = ggd.tower_menu_grid` 再取 `grid.cols` → `attempt to index local 'grid' (a function value)`，
崩在 `E:load`（菜单模块体末尾就会调 setup）→ 整个插件被**自动禁用**。

**2. 收纳是黑名单：除 4 种之外全进网格**（`all-desktop/game_gui.lua:8389-8402`）

```lua
local non_grid_actions = {"tw_sell", "tw_rally", "tw_point", "tw_change_mode"}
local function is_grid_item(item) return not table.arraycontains(non_grid_actions, item.action) end
local use_grid = #grid_items > math.min(grid_config.cols * grid_config.rows, 15)
```

⇒ `tw_buy_attack` / `tw_unblock` / 自定义 action **都会进网格**。插件要做的事只剩"提供按钮"：
滚轮（`TowerMenu:scroll_grid` → `grid_list:scroll_by`）、翻页箭头、深色圆角底板、`image_ss = nil`
全是本体做的。**自己再分页会和本体打架**：每页只交 N 个 → 若 N ≤ 15 则 `use_grid=false` 退回环形平铺，
且 `scroll_grid` 钩子会吃掉滚轮（`game_gui.lua:875` 那条 `return true`），本体网格收不到。

**3. 但 `item.place` 仍然必须有效** —— 这是最容易以为"网格模式下不用 place"的地方：
`TowerMenu:show` 末尾的"统一处理菜单可视性"（`game_gui.lua:8573` 附近）对**所有非 `tw_upgrade`** 项读
`data.tower_menu_button_places[item.place].x`，nil 就 `attempt to index` 崩（和当年 `V.vclone(nil)` 同源）。
所以要在 places **末尾 append** 自己的槽位（绝不要覆盖本体已有的 1..N，那是全局共享表）：

```lua
local base = ggd._<plugin>_slot_base
if base and #places < (ggd._<plugin>_places_len or 0) then base = nil end  -- 本体截短就重申请
if not base then base = #places; ggd._<plugin>_slot_base = base end
for i = 1, count do
    if not places[base+i] then
        local idx, row, col = i-1, math.floor((i-1)/grid.cols), (i-1) % grid.cols
        places[base+i] = v(grid.view_pos.x+(col+0.5)*grid.x_unit, grid.view_pos.y+(row+0.5)*grid.y_unit)
    end
end
```

槽位键必须带插件前缀，否则两个同类插件（`mercenary_tavern` / `mercenary_tavern_basic`）会抢同一段。
参考实现：`mods/local/mercenary_tavern/mercenary_tavern_menu_layout.lua`（26 按钮 → place 25..50）。

**4. 自查清单**（改完跑一遍，都不用进游戏）
- `#items > min(cols*rows, 15)` 成不成立？不成立就**不会**进网格（按钮会回到 `place` 定位的环形布局）。
- `places[每个召唤项的 place]` 是否全非 nil？
- 有没有残留的自建分页钩子（`button_callback` / `scroll_grid`）？有就删。
- 两版共存时各自的 `_slot_base` 是否错开（local 25..50 / basic 51..67）？

## 伤害结算与条件加伤（damage_hooks）

1. 结算链：`SU.create_bullet_damage` 把 `bullet.damage_hooks` 挂到 `d.hooks`（script_utils.lua:607）→ `U.predict_damage`（utils.lua:2000）在**算护甲减伤之前**遍历 `damage.hooks[i](entity, damage, protection)`，钩子可直接改 `damage.value` 实现条件加伤。
2. 护甲字段：`health.armor`（物理，0~1 比例）/ `health.magic_armor`（components.lua:34-35）；物免判定 `band(health.immune_to, DAMAGE_PHYSICAL) ~= 0` 视作满甲。`health.armor` 会被 `SU.armor_dec` 永久削减。
3. DAMAGE_ARMOR / DAMAGE_MAGICAL_ARMOR 走 `armor_dec` 分支，不进 hooks。
4. 条件加伤模板：
   ```lua
   local factor = 1.2
   local function hook(entity, damage)
       local h = entity.health
       if not h or band(h.immune_to or 0, DAMAGE_PHYSICAL) ~= 0 then return end
       if (h.armor or 0) - (damage.reduce_armor or 0) <= 0 then
           damage.value = damage.value * factor
       end
   end
   tt.bullet.damage_hooks = { hook }
   ```
   子模板 `RT(name, 父)` 会继承 `damage_hooks`（父模板挂一次即可）；自写光环/AoE 用 `E.assign_damage` 时需手动 `d.hooks = HOOKS`（默认 `hooks={}`）。钩子按"命中的每一跳"判定，多段箭/克隆箭/AoE 各自独立。
5. 运行时改倍率：scripts 模块 `return scripts`，主入口 `require` 后调暴露的 setter 改闭包 upvalue（模板每次 `E:Load` 重新注册，闭包同步刷新）。
6. **想要"命中后范围伤害 / 转真实伤害 / 落地印记"** → 基模板（如 `scripts.shotgun.update`）**不消费 `bullet.damage_radius`**，别改引擎；用「薄包装模板 `main_script.update`」范式，详见技能 **`kr-dove-bullet-aoe-fx`**（含 `SU.create_bullet_damage_without_pops` 入队口径、暴击污染坑、常驻图集查帧法、离线断言配方）。
6-bis. ⭐⭐ **近战"每次结算加伤/暴击"用 `attack.fn_damage`，别包 `update`、更别换全局函数**（2026-10-02 reinforcement_more_choice 定稿）：
   - **原生挂点**：`attack.fn_damage(this, store, attack, target)` → 返回值**直接作为最终伤害**。两条路径都支持：
     loopable 非 area 分支 `all/script_utils.lua:2261`、单目标分支 `:2382`。
     ⚠ **area 分支（`:2211`）不支持** `fn_damage`，只认 `damage_min/max`。
   - ⚠⚠ **返回值口径**：引擎**不再**乘 `unit.damage_factor`、**不再**加 `unit.damage_buff`（对比 `:2264` 原路径 `damage_factor * (random + damage_buff)`）⇒ 自定义函数里必须**自己补齐**，否则伤害会少一截：
     ```lua
     atk.fn_damage = function(this, store, attack, target)
         local v = math.random(d_min, d_max)
         if math.random() < crit_chance then v = v * crit_mult end
         return this.unit.damage_factor * (v + this.unit.damage_buff)
     end
     ```
   - **多段攻击（`hit_times = {…}`）每段各调一次 `fn_damage`** ⇒ 天然实现"每段独立掷骰"，正好符合直觉。
   - ❌ **不要包 `update` 做临时改值**：`scripts.soldier_reinforcement.update` / `hero_*` 这类 update 是**协程体**（内部 `coroutine.yield`）。在外部 `pcall(update_orig, ...)` 后还原伤害字段，会在 yield 挂起期间**一直保持放大**（且每帧重掷），变成"整段存活期全程暴击"。同 `kr-dove-tower-port` 第 12 条 buff 冻结坑同源。
   - ❌ **不要替换全局 `SU.y_soldier_melee_block_and_attacks`**（2026-10-02 之前 reinforcement_more_choice 就这么干）：即便用 `this._flag` 守卫限定本单位，仍是对**全局函数**动刀 —— 其他插件/单位一旦也动它就会互相撕；且 `plugin:unload` 不还原。改成挂在本单位模板的 `attack.fn_damage` 上，零污染。
     （附注：插件里写 `SU.xxx` **不需要**自己 require —— `plugin/plugin_globals.lua:41` 注入了全局 `SU`。别因为"没看到 require"就误判成 bug。）
   - ⚠⚠ **但「注入的全局」是双刃剑：与引擎同名模块撞车**（2026-10-03 sorcerer_split_shot 定稿）。
     `plugin_globals.lua` 往全局塞了一批 helper：`AC(name,...)`=`E:add_comps`（`:74`）、`RT`、`CC`、`T`、`E`、`U`、`SU`、`fts`、`d2r`…
     而引擎里**同名 local** 常是**完全不同的东西** —— 最典型 `AC`：
     | 场合 | `AC` 是什么 | 定义 |
     |---|---|---|
     | 引擎各文件 | `achievements` 模块（`A:inc_check(id,value)`） | 每个文件自己 `local AC = require("achievements")` |
     | 插件全局 | 模板 helper 函数 `E:add_comps` | `plugin/plugin_globals.lua:74` |
     ⇒ 插件里想用**引擎语义**的 `AC`（如 `AC:inc_check("SHEEP_KILLER")`），**必须文件级 `local AC = require("achievements")` 遮蔽**；
     否则命中的是 helper 函数 ⇒ `attempt to index global 'AC' (a function value)`（index a function 立即崩）。
     ⚠ **不能全局改名** —— 插件主入口用 `AC(tt,"render","dps")` 调 helper 的地方不能动（`sorcerer_split_shot.lua:235/:385` 实证）。
     ⚠ **照抄原版函数体时，文件顶部的 local require 区必须一并抄**（`:1247-1263` 逐行抄了 `kr1/game_scripts.lua:1360-1371`，
       唯独漏抄第 4 行 `local AC = require("achievements")` ⇒ 崩）。这是「抄代码漏开头」类 bug 的通用形态。
     ⚠ `require("achievements")` 在插件环境可行：`main.lua:114 search_roots` 含 `"all"` ⇒ `all/?.lua` 命中；
       `plugin_main.lua:7` 是把插件路径**前置追加**到 `FS.getRequirePath()`，不自建独立路径。
     排查口令：见 `attempt to index global 'X' (a function value)` / `attempt to call global 'X' (a table value)`
       ⇒ 先 `grep -n "function X\|X =" plugin/plugin_globals.lua` 看是不是被注入占了。

7. ⭐⭐ **回血没有 `U.heal` 这类 API**（旧笔记曾误记 `utils.lua` 有 `U.heal`/`U.heal_with_overflow`，**实际不存在**）。
   引擎官方回血写法 = **直改 hp + clamp**（`all/scripts.lua:5343`，`scripts.mod_hps.update`）：
   ```lua
   local hp_start = target.health.hp
   target.health.hp = target.health.hp + amount
   target.health.hp = km.clamp(0, target.health.hp_max, target.health.hp)
   target.health.hp_healed = (target.health.hp_healed or 0) + (target.health.hp - hp_start)
   ```
   - ⚠ `signal.emit("entity-healed", this, target, heal_amount)`（`:5350`）**全库没有任何监听者**；
     `health.hp_healed` 也**无消费点** ⇒ **回血不会有飘字**。想要飘字得自己造。
   - ⚠ **满血时通常直接 return / 不回**（`mod_hps.insert` 就这么早退），免得白刷 `hp_healed`。
   - 按**最大生命值比例**回血：`amount = target.health.hp_max * ratio`
     （`hp_max` 就是实战上限，血条分母直接用它，`systems.lua:3273`；无额外乘算层）。
   - ⭐ **按比例「削减」最大生命**（debuff / 侵蚀类被动 —— `weird_archer` 灵魂印记 · `hero_zezitra` 黑魔侵蚀同款）：
     **不是直接掉血**，而是**按当前血量比例缩放**：
     ```lua
     local hp = (type(target.health.hp) == "number") and target.health.hp or hp_max
     local ratio = hp / hp_max
     target.health.hp_max = hp_max * (1 - cut)      -- 永久压低上限
     target.health.hp     = target.health.hp_max * ratio
     ```
     ⇒ 血条**百分比不变**、上限被永久压低、**可乘算叠加**（打 N 次剩 `(1-cut)^N`）。
     ⚠ 只能对 `hp_max` 是**数值**的实体做（个别敌人 `hp_max` 是**数组**，按等级/难度取 ⇒ 乘法崩，
     必须先 `type(hp_max) ~= "number" ⇒ 跳过`）。触发点两处：近战命中挂 `melee.attacks[n].side_effect`
     （签名 `(this, store, damage, target)`，`all/script_utils.lua:2391` 调）；远程命中在弹丸/射线**伤害结算段**手动调。
     （范式实现在 `hero_zezitra/scripts/hero_scripts.lua` 的 `erode_target` / `erode_side_effect`。）
8. ⭐⭐ **短时减伤/增伤 buff —— 用「每帧幂等同步」而不是 mod 实体**（2026-10-01 ember 业火减伤实战定型）：
   - 字段是 **`health.damage_factor`（默认 1，`all/components.lua:39`）= 承受**伤害倍率；消费点 `all/utils.lua:2051`：
     `dvalue = dvalue * entity.health.damage_factor * (1 - protection) + against_extra`
     ⇒ 减伤 8% ⇔ 设 `0.92`。⚠ 与 **`unit.damage_factor`（输出**伤害倍率，攻击方）**完全两回事**，`damage_hooks` 里那个是输出侧。
   - 原版范式（`kr1/hero_scripts.lua:31002` `mod_hero_dragon_arb_ultimate`）是 mod 实体 insert 时 `*= f`、remove 时 `/= f`。**但短暂 buff 别照抄**：
     `modifier` 组件默认 `replaces_lower=true` / `resets_same=true`（`components.lua:877-878`），
     `all/systems/mod_lifecycle.lua:63-99` 里 `resets_same` 只重置 `m.modifier.ts`；**`replaces_lower` 走 `queue_remove_entity`（延迟到 `simulation.lua:200-212` 帧末批处理）**
     ⇒ 旧 mod 的 remove（除法还原）**晚于**新 mod 的 insert（乘法）⇒ 升档算出错值（实测 8%→12% 得 `0.88/0.92 ≈ 0.9565` = **约 4.3%**）。
     且 `game.simulation_systems` 里 `mod_lifecycle` 排在 `main_script` **之前**、`insert_entity` **任一 system 返回 false 就 return**（`simulation.lua:250-254`），时机更难控。
   - **正解**：触发时只**记字段**，由实体自己的 `update` 循环**每帧幂等写**：
     ```lua
     -- 触发点（任意次数/任意顺序都对）
     h.dr_ratio = arr[skill_lvl] / 100
     h.dr_until = store.tick_ts + dur            -- ⚠ tick_ts 单位是【秒】，不换算帧
     -- 每帧（放在主循环汇合点、yield 之前）
     local r, base = h.dr_ratio, h.dr_base
     if r and r > 0 and h.dr_until and store.tick_ts < h.dr_until then
         if base == nil then base = h.damage_factor; h.dr_base = base end   -- 首次进入快照
         local want = base * (1 - r)
         if h.damage_factor ~= want then h.damage_factor = want end          -- 值相等不写，避免无谓标脏
     elseif base ~= nil then
         h.damage_factor = base; h.dr_base = nil; h.dr_ratio = nil; h.dr_until = nil
     end
     ```
     - **`dr_base` 快照**是关键：保住外部在创建期写进去的倍率（`all/level_utils.lua:416` 的 `hero_health_damage_multiplier`、`script_utils.lua:4830` 的缩放），直接 `= 0.92` 会把它们抹平回 1。
     - 幂等 ⇒ **刷新时长 / 取最高档 / 叠加** 全变成改字段策略，与触发次数和顺序彻底解耦；不会出现"乘了几次"。
   - **字段挂 `health`（`h = this.health`）而非 `this.attr`**：英雄死亡重生会重建 health ⇒ buff 不跨命残留。
   - 组合增益想**相乘**时：`base * (1-r1) * (1-r2)`（各部分独立快照），不要写成 `base - r1 - r2`。
9. ⭐⭐ **固定点数加伤 —— 用 `unit.damage_buff`（累加 + 截断），不要用 `damage_factor` 硬凑**（2026-10-01 ember 硬化拳定稿）：
   - 字段 **`unit.damage_buff`（默认 `0`，`all/components.lua:391`）**，语义 = 在 min/max 上**加一个固定点数**。
     官方 API `SU.damage_inc(this, v)` / `SU.damage_dec(this, v)`（`all/script_utils.lua:346/355`）
     实质就是 `this.unit.damage_buff = this.unit.damage_buff ± value`。
   - **消费点**（各攻击路径都要自己确认一遍）：近战 `all/scripts.lua:530`
     `min, max = a.damage_min + this.unit.damage_buff, a.damage_max + this.unit.damage_buff`；
     远程弹丸 `script_utils.lua:1532/1678`，`E.assign_damage` 类在 `:707/:1097/:1400/:2047/:2211/:2264/:2383` 等。
   - ⚠ **别和 `health.damage_factor` 混**（第 8 条）：`health.damage_factor` 是**承受**侧倍率（乘法），
     `unit.damage_buff` 是**输出**侧点数（加法）；`unit.damage_factor` 则是输出**倍率**。三者互不相同。
   - ⚠ **`unit` 组件在死亡重生时不会被重建**：`SU.y_hero_die`（`script_utils.lua:1156-1205`）只重置
     `health.hp` / 位置 / 动画 / `health_bar` ⇒ `damage_buff` **跨死亡保留**。
     想做"死亡清零"得自己在重生钩子里手动 `SU.damage_dec(this, cur_value)`。
   - **capped 叠加的写法 = 增量 + 截断**（原版范例：熊猫鑫「驭体于灵」`kr1/hero_scripts.lua:15757/15804/15905-15907`，
     另存 `mind_over_body_damage_buff_max`，进入 `+`、退出精确 `-`）：
     ```lua
     local cur = this.hero.<skill>_bonus or 0
     if cur >= cap then return end
     local add = per
     if cur + add > cap then add = cap - cur end   -- 最后一段只加差额
     this.hero.<skill>_bonus = cur + add
     SU.damage_inc(this, add)
     ```
     - ⚠ **别写"幂等重算到目标值"**（如 `SU.damage_inc(this, cap - cur)` 一次性拉满）：
       会把**外部光环对 `damage_buff` 的贡献**一起算进 `cur`，或反过来把它抹掉。
       增量 + 自存 `*_bonus` 计数器 ⇒ 只在**自己**那一份上做加法，外部加成原样保留（探针里有专项断言）。
     - ⚠ 探针算期望时注意**截断**：`cap=12`、已有 `8`、每次 `+3` ⇒ 第 1 次得 11、第 2 次得 **12**（不是 14）。
       这一条我自己写错过一次（是探针错，不是代码错）。
10. ⭐⭐ **一个 hook 字段只能挂一个函数 —— 多机制必须串「总入口」**（2026-10-01 ember 实测）：
   - `tt.melee.attacks[1].side_effect` 这类字段是**单值**，第二次赋值 = **覆盖第一次**，不报错、不警告。
     给英雄加第二个"普攻命中触发"的机制时，若直接改这个字段，**旧机制会静默消失**。
   - 正解：改成一个**总入口**分发函数，各机制是它内部的子函数：
     ```lua
     function scripts.<entry>_melee_side_effect(this, store, d, target)
         scripts.<entry>_<mechanism_a>(this, store, d)
         scripts.<entry>_<mechanism_b>(this, store, d, target)
     end
     -- 模板侧只写一次：tt.melee.attacks[1].side_effect = scripts.<entry>_melee_side_effect
     ```
   - ⚠ **参数按最宽的那个传**（有的子函数要 `target`、有的不要），别按窄的那个省参数。
   - ⚠ 落在 `scripts` 全局表上的函数（引擎脚本文件常无 `return`），**必须在 `E.Load` 之后取**；
     校验脚本要断言"模板字段 == 总入口名" **且** "总入口体内同时调用了 A 和 B" —— 只断言字段名会漏掉覆盖回归。
11. ⭐⭐ **「限时的固定点数 buff」= 计数器 + 到期清零 + 刷新**（2026-10-01/02 ember 硬化拳定型）：
   需求形如"每次命中 +N 点，上限 M，**只保留 X 秒**，每次命中刷新"。
   - **叠：增量 + 截断**（同第 9 条）：`add = min(per, cap - cur)`；`cur` 用**自存计数器**，别重算。
   - **刷新窗口**：命中时 `until = store.tick_ts + duration`。
     ⚠⚠ **必须写在"已到上限就 return"的早退之前**，否则叠满后继续攻击不再续窗
     ⇒ 停手前最后一次命中不算数 ⇒ **满层加成提前掉光**（很容易漏，且只在满层+边缘时刻才显形）。
   - **到期清零**：`SU.damage_dec(this, 计数器值)` —— **精确收回自己加过的那一份**。
     ⚠⚠ **绝不能**写"把 `damage_buff` 归零"：那会把**外部光环写进同字段的加成一起抹掉**。
     清完把计数器置 0、`until` 置 nil ⇒ 这是**一次性事件**，重复同步不会二次扣。
   - **判断用 `>=`**（`tick_ts >= until` ⇒ 到期），与"刚好等于"的边界保持确定性。
   - `duration <= 0` 留作"关闭限时"档（退化成永久叠加），描述里也要跟着**不拼**"持续X秒"。
12. ⭐⭐ **buff 计时别只挂在主循环末尾的汇合点 —— 内层等待路径会把它冻住**（2026-10-02 ember 踩到）：
   一个挂着"每帧同步"的短时 buff（减伤 / 限时叠攻）如果只在 `while true` 循环**末尾**同步，
   那么主循环里**所有内层等待路径**（技能动画等待、引导期 cast/shoot/开火循环）`yield` 之后
   **都不会经过那个汇合点** ⇒ 计时在这些路径里**完全冻结**。
   症状极隐蔽：短暂动画里看不出来，一旦引导时长（数秒）≫ buff 时长（几秒），
   就表现为"buff 打不散 / 时间到了还挂着"。
   - **正解**：把本协程里**所有**等待收敛成一个局部闭包，同步动作和 `yield` 绑在一起：
     ```lua
     local function wait_frame()
         ember_sync_damage_reduction(this, store, h)
         ember_sync_hardened_fist(this, store)
         coroutine.yield()
     end
     ```
     然后把协程内**每一处** `coroutine.yield()` 换成 `wait_frame()`。
   - ⚠ 用**源码结构断言**把这条钉死，因为离线 harness 跑不了 tick：
     切片 `hero_<x>.update` 的函数体（`find('function scripts.hero_x.update')` 到下一个
     `function scripts.` 的位置）→ 先去掉行内注释（`body:gsub('%s*%-%-[^\n]*','')`）再数：
     裸 `coroutine.yield` 应**恰好 1 处**（`wait_frame` 内部），`wait_frame` 应 **≥ 定义+各调用点数**。
   - ⚠ 加**新等待分支**时忘了用它 = 这条纪律失效，代码注释里要写明"别再写裸 yield"。
13. ⭐⭐ **同一个数值往往有两份「住址」：技能表 vs 定时攻击条目** —— 代码读哪份就要往哪份写
   （2026-10-02 ember 火山 `refund` 实战，症状是"面板调多少都没用"）：
   - 典型结构：数值的**权威配置**落在 `tt.hero.skills.<x>.<field>`（技能表），
     而运行时脚本读的却是 **`this.timed_attacks.list[n].<field>`**（定时攻击条目）。**两张不同的表**。
     `level_up` 必须**逐字段搬运**（ember 火山搬了 `cooldown` / `shots`，唯独漏了 `refund`）。
   - ⚠⚠ 漏搬的后果**完全静默**：`a.refund` 恒 nil ⇒ 下游 `a.refund or 0` = 0
     ⇒ 若它是个"上限/封顶"参数，`math.min(x, 0)` **恒 0** ⇒ 功能整体失效，
     且**面板上的每一项调整都不会有反应**（不报错、不崩、不打印）。
   - **症状识别**：某个"上限/系数"类配置**改了完全没反应**时，先怀疑**读的字段根本不是写的那份**，
     而不是公式错。查法：`grep -n "<字段名>" <插件目录>`，看**写入点**与**读取点**的表名是否一致。
   - **探针配方**（`.workbuddy/probe_ember_skill_fields.lua`，通用）：
     拿**真模板**当 `this` 桩（`E:get_template('hero_<x>')`）→ 跑一遍**真 `level_up`**
     → 再逐个核对 `timed_attacks.list[n].{...}` 的实际值 == 配置值。
     ⚠⚠ **等级要取「技能解锁档」**（如 volcano 的 `xp_level_steps = { [3]=1,[6]=2,[9]=3 }` 要取 3/6/9）：
     取一个**不在表里**的等级（如 10）⇒ `sl` 为 nil ⇒ **整个技能块被跳过** ⇒ 探针会把
     "所有字段都没写"误报成 bug。这个坑我踩过一次（第一版探针用 10 级，全字段 nil）。
     顺带把公式**用真值复算**一遍并与 README 的查表对拍。

## 冷却控制（返还 / 加速）与「比例化」折算

1. **冷却的判据与入口**：`timed_attacks` 条目上的 `a.ts`（上次施放时刻）。
   可施放条件 `store.tick_ts - a.ts > a.cooldown`（或 `>=`，各技能不一，照抄原脚本）。
   ⇒ **缩短冷却 = 把 `a.ts` 往前移（减）**；写成 `+` 会**加长**冷却（2026-10-01 ember 火山实测踩过）。
   `a.ts = start_ts - cooldown * ratio` ⟺ 返还 `cooldown × ratio` 秒（下次可施放在 `start_ts + cd*(1-ratio)`）。
2. **"引导期被提前打断"的通用结构**：把 `a.ts` 的赋值**延后到引导结束**，用一个 `interrupted`
   标志区分「自然打完」（`a.ts = start_ts`，完整冷却）与「提前结束」（`a.ts = start_ts - cd*ratio`）。
   - ⚠ `interrupted` 要在**最早的 goto/break 之前**声明（Lua 的 `goto` 不能跳进 local 的作用域：
     `<goto L> jumps into the scope of local 'x'`）；若把 goto 改成 `break` 落穿，这个约束就没了。
   - ⚠ 尾部兜底用 `if not interrupted then a.ts = start_ts end`，**别再叠 `started == 1` 之类前置**：
     引导循环体才置位的标志一旦漏置，`a.ts` 会停留在**上一次施放**的时刻 = 白送一段冷却。
   - ⚠ 别让某条退出路径 `goto` **跳过**返还块：那会变成"0 发射却拿不到返还"的静默缺口。
3. ⭐⭐ **可调数值的折算一律用「比例」，不要用「绝对值」**（2026-10-02 ember 火山冷却返还定稿）：
   凡被折算的量，其基数若**玩家可调**（炮弹发数、技能等级、持续时间…），就必须写成
   `剩余 ÷ 总量` 这类**无量纲比例**再乘系数。
   反例：按"每少打一发免 X 秒"折算 —— 玩家把 `shots` 从 6 调到 20，单发价值立刻缩水到 1/3。
   正解：`ratio = (total - fired) / total`，与总发数无关（`shots=20` 打满一半仍恰免 50%）。
4. **上限与特例要分层写，别混进一个表达式**：
   ```lua
   if fired <= 0 then
       ratio = 1.0                                      -- 特例：完全没收益 ⇒ 全免（无视上限）
   else
       ratio = math.min((total - fired) / total, cap)    -- 常规：封顶
   end
   ```
   ⚠ 若把特例塞进同一个 `math.min` 表达式，一旦 `cap` 被玩家调小，特例会静默失效。
   ⚠⚠ **`cap` 这个变量必须来自"读的那张表"**：ember 火山的 `cap` 读的是
     `timed_attacks.list[n].refund`，而配置只写到技能表 ⇒ 恒 nil ⇒ `or 0` ⇒
     `math.min(..., 0)` **恒 0** ⇒ 只要发射过 ≥1 发就**一分不返**，且面板调多大都没反应。
     详见第 13 条「同一个数值两份住址」。
     （ember 火山的**出厂默认** `skill_volcano_refund` = **0.8**，2026-10-02 用户定稿；此前为 0.6。
      ⚠ 用户实机调的 AppData 值可能与之不同 —— 那是他们的实时配置，别当成默认值。）
   ⭐ **"已发射几发"的记账口径要与玩家看到的画面一致**：炮弹有"动画起手 → 弹丸生成"的
     windup（ember 火山是 `shoot_time`），玩家在这中间撤走时会觉得"它明明开火了"。
     做法：炮台侧加一个**只读提示位**（起手置 `firing = true`、弹丸入账后清掉），
     英雄侧 `fired = shots_fired + (firing and 1 or 0)` 并**封顶 total**。
     ⚠ **别**用同一个计数器提前自增 —— 若 `shots_done` 跟着提前置位，炮台会少打最后一发。
5. **数值探针怎么断言**（内嵌在永续协程里的公式没法直接调用）：**源码结构断言 + 公式复算**双管齐下 ——
   ① 断言真实源码含特征串（如 `'math%.min%(%(total %- fired%) / total, a%.refund or 0%)'`）**且旧口径特征串已消失**（防回退）；
   ② 用同构公式复算期望表并与 README 数字对拍。范式见 `.workbuddy/probe_volcano_refund.lua`。
   ③ ⭐⭐ **别把「会被用户改的数值」写死进探针** —— 写死的一定会随用户调平衡腐烂成**假红**
     （2026-10-02 一天踩了两次：`xp_gain_factor` 1.1→1.13 两处期望过期；`probe_ember_volcano_idle_refund`
     更惨，整条公式是旧版 ⇒ 6 条 FAIL 全是假的）。做法：
     - **能在运行时读到的量就当基准**：`local XPF = B.xp.gain_factor`，再 `expect = round(100 * XPF * MULT)`；
       用户改值后探针自动跟随，只有 README/config 需要更。
     - **只有不变量才配写死**：`a.ts` 必须**减**、`ratio ≤ refund`、"已发+剩余 = 1"。
     - **公式型探针（纯算法复算、不跑 tick）必须逐字照抄源码**，并在头部注明「源码改公式则本探针必须同步」；
       源码里"旧版 XXX 不公平 ⇒ 已统一"之类的注释，就是探针没跟上的信号。
     - ⚠ 报 FAIL 时**先查代码/配置实际值**再动手：若 config / `balance.lua` DEFAULTS / README **三处一致**，
       那就是**用户改动 + 脚本过期**，改脚本、别改代码（反面案例：`a.refund` 漏搬运才是真代码 bug，
       判别法见第 13 条 —— 那里"三处不一致"）。

## 科技树（天赋）注册——自定义塔吃到加成的必要条件

所有职业科技都由 `UP:patch_templates()`（`kr1/upgrades.lua:1535`）遍历 `archer_towers` / `arrows` 等列表**改模板**实现，调用点在 `all/systems/level.lua:99`（`E:Load` 之后）。所以：

1. **同时写两张表**：`GS.<class>_towers`（`kr1/game_settings.lua`）和 `UP.<class>_towers`。`upgrades.archer_towers = GS.archer_towers` 名义上是同一张表，但 `archer_critical` 直接用 `GS.archer_towers`，任一份被重建都会漏条目。
2. **所有箭矢模板都要单独登记进 `UP.arrows`**：`patch_templates` 只改列表里点名的模板，子模板（`RT(name, 父)`）注册时已克隆完毕，穿刺/黑曜石/裂伤/魔法箭这些改 `bullet` 的科技不会从父模板传导。
3. **在 `hook:init` 和 `hook.E.load` 里都调用**，不能只在插件 init 注册一次（列表可能随 `E:Load` 被重建）。
4. 登记后会吃到：鹰眼/远射=射程、致命一击/飞行克星=`tower.damage_factor`、穿刺=箭矢 `reduce_armor`、黑曜石=箭矢 `damage_hooks` 追加、裂伤/魔法箭=箭矢 `mods`、急速射击=`cooldown_factor`+精灵 fps、伐木=特技价、回收=建塔价。
5. **与"配置写模板"的冲突**：`patch_templates` 每关只跑一次，热更新配置若把射程/价格写回基础值会冲掉科技加成 → 热更新分支传 `keep_tech=true`，用 `UP:get_upgrade(...)` 手动补回倍率；关卡正常加载传 nil 交给 `patch_templates`，否则双倍加成。
6. `tower.damage_factor` / `tower.cooldown_factor_divider` 组件默认都是 1（components.lua:398-400），自定义塔不会因缺字段崩。

### ⭐⭐ 塔技能冷却必须乘 `tower.cooldown_factor`（漏了就只有普攻吃攻速加成）

本体所有"每隔 X 秒"的塔技能都走引擎收口点，它们**都会乘塔的冷却系数**：

- **技能**：`U.tower_ready_to_use_power(pow, power_attack, store, tw)`（`all/utils.lua:3643-3645`）
  ⇒ `store.tick_ts - power_attack.ts > power_attack.cooldown * tw.cooldown_factor`。**优先直接调它**，别自己写比较式。
- **普攻**：`local function ready_to_attack(attack, store, factor) → * (factor or 1)`（`kr1/tower_scripts.lua:50`），调用处传 `tw.cooldown_factor`。
- `tower.cooldown_factor` 组件默认 1（`all/components.lua:399`）；`entity_db.lua:577-579` 在载入时按难度重写为 `1 / tower.cooldown_factor_divider`。
- 玩家侧"攻速加成"（侏儒技术 / 战鼓光环 / 无尽科技 …）走 `SU.insert_tower_cooldown_buff(ts, target, factor)`
  （`all/script_utils.lua:4524`）：`divider += (1 - factor)`、`cooldown_factor = 1 / divider` ⇒ **`cooldown_factor < 1` = 更快**；`remove_...`（:4598）反向。
- ⇒ 自己写的技能计时（`cfg.<x>_cooldown[lvl]`、`cfg.<x>_interval` 这类）**必须补 `* (tw.cooldown_factor or 1)`**，
  否则只有普攻吃到攻速加成、技能照旧。2026-10-15 扫 18 个塔插件，命中 6 个漏点：
  Demon_Sentinel 技能2/3、weird_archer 符文禁锢、toxic_tomato 魔法花/食人花、TrollAxeThrower 战鼓敲鼓、
  VoidFavor 剧毒喷吐、alien_bug_nest 异星来客孵化 + 收割者狂怒脉冲。
- **反例（不要乘）**：`timed_actions.list[*].cooldown`（`SU.y_soldier_timed_actions` 裸比较）、
  士兵/子单位自身冷却（乘 `unit.cooldown_factor`）、召唤物的攻击冷却、
  `balloon_crash` 那种"只 `power.cooldown = 15` 赋值、运行时从不消费"的字段。
- 已经标准的 5 个：Shining_Holy_Nuclear_Tower、leaf_vein_archer（自带 `ready_to_use_power`）、
  movable_wild_magus、sorcerer_split_shot、sparking_geode_enhanced（后三者直调引擎）。
- 文案侧：`docs/ai_tips/PROJECT_CONTEXT.md:295-299` 要求"塔的「每隔 X 秒」一律乘 `tcd`"——
  那是渲染期求值的 DSL；用静态 `string.format` 生成的描述只能写**基础值**，别把系数算进字符串。
- 自建塔若在模板里显式写 `tt.tower.cooldown_factor = 1`，注意 `entity_db.lua:578` 载入时会再覆盖一次（同值，无副作用）。

## 技能描述随配置自动生成

1. 在主入口写 `build_descriptions(v)`，用当前生效数值 `string.format` 拼 `..._DESCRIPTION_1~3` 与 `..._SPECIAL`，写进 `i18n.msgs["zh-Hans"]`。
2. 调用点：`write_values` 末尾（同时记 `_last_values`）；`register_i18n` 内若 `_last_values` 存在再覆盖一次——否则 `i18n.load_locale` 会用静态文件把生成文本冲掉。
3. 静态 `strings/zh-Hans.lua` 只作兜底（插件 init 早于首次 `E:Load`）。
4. 建造/升级菜单里的 `tt_desc` 是烘焙字符串，热更新分支要再调一次菜单注入函数重建。
5. 支数显示 = `extra_arrows + 1`（配置里存的是附加箭数）。
6. **技能伤害别用"普攻基准 + damage_inc×等级"推导**——改普攻会连带抬高技能伤害，改成 balance 里写死 `per_level_damage = {{min,max},{min,max},{min,max}}`，注册时展开到 `attacks.list[n].per_level_damage_min/max`，脚本里取 `per_level_damage_min[level]` 并置 `damage_inc = 0`；箭矢模板的 `bullet.damage_min/max` 只留 1 级值兜底（`damage_inc = 0`）。这样普攻和技能两个数值轴互不干扰。
6. **数值格式化两个坑**：① `(1.4-1)*100` 有浮点尾巴（40.000000000000006），必须先 `math.floor(n*10+0.5)/10` 再判整数；② `tostring(40.0)` 在 Lua 5.4+ 是 `"40.0"`、游戏用的 5.1 是 `"40"` → 整数一律 `string.format("%d", n)`。
7. 快速验证：`.workbuddy/check_leaf_desc.py`（lupa 跑真实 Lua）把主入口的 `num()`/`build_descriptions()` 抽出来跑，对比静态文本并改数值看是否跟着变。lupa 要点：Lua 的 `io.open` 在中文路径报 Illegal byte sequence → 由 Python 读文件再 `load(src)`；`lua.execute` 的 local 不进全局 → 用 `load(src .. " return fn")()` 导出。
8. 写完含 `%` 的 Lua/文本要回读校验（曾出现 `20%` 被吞）。
9. ⭐⭐ **英雄殿堂的技能描述（`hero_room_special`）是另一套，别和塔描述混**（2026-10-01 ember 实战）：
   - **冷却必须显式给**：原生 `_assets/kr1-desktop/strings/hero_room_special.lua:96-97` 的
     `get_cooldown()` 直接读 **`s.cooldown[max_lvl]`**（`s` = 当前技能模板表），再由 `:205-206` `cooldown_str()`
     套 `HERO_ROOM_FMT_COOLDOWN`（zh-Hans：`"每隔%s秒，"`）拼在描述开头。
     ⇒ 技能模板里**没有 `cooldown` 字段，殿堂描述就整个缺冷却**（该字段对部分技能是"纯展示"的，不驱动任何计时，
     但只要它存在，原生逻辑就会写）。
   - 插件里手写殿堂文本（如 `scripts/hero_room_texts.lua`）时要**自己拼这句**，写法照抄口径：
     `"每隔" .. str(cooldown_arr[满级]) .. "秒，"`。
   - ⚠⚠ **`top(arr, fallback)` 的 fallback 也是要跟改的**：描述里的数值若写成 `top(hf.heal_ratio, 0.1)`，
     改配置为 `0.14` 后描述仍会（在某些路径下）显示旧值 —— fallback 只在数组缺失时生效，但**改数值时极易漏改**，
     实测就漏了一次（描述显示 10%、实际 14%）。
   - ⚠ **新增能力 / 改机制时都容易漏改描述**（改数值那一类见上一条的 `top()` fallback）：
     校验脚本通常只查 config / balance / 模板契约，**不查"描述生成出来的文本"**。
     2026-10-02 的典型：硬化拳从"永久叠加"改成"只保留 4 秒"，描述里那句「**永久**提升」
     必须一起改成「持续4秒；每次命中刷新持续时间」—— 否则描述直接说谎。
     ⇒ 加一个**打印文本的探针**（`.workbuddy/probe_room_text.lua` 范式：直接 `require` 描述模块并 `print` 每条）
     然后**目视一遍**；再把关键措辞做成**断言**（如"不得含『永久』+ 必须含『持续4秒』"），防下次回归。
     这一轮就是靠目视 + 断言抓到两个既有 bug（百分比错、新能力没写进文案）和一次改机制的漏改。
   - ⭐⭐ **文案风格口径（写描述前先读这 9 条，全部实证自 `zh-Hans.lua`）**：
     ① 伤害一律 **`<数值>点<类型词>`**（`HERO_ROOM_FMT_DAMAGE = "%s点%s"`），
        类型词取 `HERO_ROOM_DMG_*`：`爆炸伤害` / `真实伤害` / `物理伤害` / `法术伤害`。
        ⚠ **绝不能写「造成35」这种裸数字**，也不能自己造「点无视护甲的真实伤害」——
        `点真实伤害` 本身就含真伤语义。
     ② 范围一律 **`<数值>范围内敌人`**（全库 103 处），⚠ **不加「的」**，不写「范围内所有敌人」。
     ③ 冷却前缀 **`每隔%s秒，`**（`HERO_ROOM_FMT_COOLDOWN`），放句首。
     ④ 回血一律 **`恢复%s%%最大生命值`**（见 `HERO_ROOM_IGNUS_FLAMING_FRENZY_DESC`）；
        单值生命写 **`%s点生命值`**（`HERO_ROOM_FMT_HP`）。
     ⑤ 减速一律 **`并使其受到%s%%的减速效果`**，⚠ 不写「移动速度降低X%」。
     ⑥ 眩晕写 **「眩晕」**，⚠ 不写「击晕」。
     ⑦ 英雄自称原生一律用 **「英雄」**（兼容她/他双性别，原生大量这么写）；
        ⚠ 但**本插件（ember_hero）用户 2026-10-01 明确要求改用英雄名「余烬」** ⇒ 该插件文案口径以「余烬」为准，
        别照抄本条把它改回「英雄」。
     ⑧ 句式直述、不堆辞藻；原生会长到 200+ 字且用分号连缀多个效果，这是**正常的**。
     ⑨ 数值来源统一：数组取满级（`arr[#arr]`，与原生 `ss(key) = s[key][max_lvl]` 同口径），
        百分比 = `math.floor(x*100+0.5)`，小数最多 2 位去尾零（`str()`）。

## 游戏内配置面板（数值可调）

参照 `arcane_archer_custom` 模式：

1. 配置值文件命名 `<entry>_config.lua` 放插件根目录（require 路径 `<entry>.<entry>_config`），结构：`enabled` 总开关 + 扁平数值字段 + `key_label_map`（字段→中文标签，游戏配置面板按此渲染；标签加技能名前缀便于区分）。
2. 主入口：`E.load` 里模板注册完成后 `apply_config()`（`E:get_template(name)` 改模板字段）；HOOK `simulation.update` 每 30 帧 hash 检查配置文件变更实现热重载；`enabled=false` 时把 balance 默认值写回模板。
3. **特技价格机制**（game_gui.lua:8236/9038）：首次学习付 `power.price_base`，之后每次升级付固定 `power.price_inc`（不是逐级累加公式）。
4. 插件环境无全局 `T()` 依赖风险，用 `local E = require("entity_db")` + `E:get_template(name)`（冒号方法，entity_db.lua:403）。

## 百科全书缩略图（自定义塔）

- 原版塔缩略图源 PNG：`mods/local/资源/图集/KingdomRushDove-store/源文件/encyclopedia/`（塔 86x82，敌人 64x62）；运行时打包在 `_assets/kr1-desktop/images/fullhd/encyclopedia-1.dds + encyclopedia.luac`（组名 `encyclopedia`；敌人缩略图单独 `encyclopedia_creeps` 组）。
- 取图逻辑 `all-desktop/screen_map.lua` `EncyclopediaView:load_towers`：tower_data 条目有 `thumb_image_name` 直接用；否则 `U.splicing_from_kr(from_kr, "encyclopedia_tower_thumbs_%04i" % t.icon)`（from_kr 决定 krN_ 前缀）。右侧详情大图 = `encyclopedia_towers_%04i`。排版目标尺寸 `encyclopedia_view_size_map.tower_thumb = v(84,78)`。
- 自定义塔做法（leaf_vein_archer 已验证）：① 图集描述补独立单帧页（a_name 写真实 .png、f_quad 全图）；② `I:add_image("xxx_enc_thumb", img, "<插件组>", scale)`，scale=显示尺寸/源尺寸（如 172x164 的 2x 图用 0.5 → 86x82）；③ hook `U.splicing_from_kr` 按名字劫持 `encyclopedia_tower_thumbs_XXXX` 返回自定义图名；④ `map_data.tower_data` 注入条目（icon 编号先查重）。参考 `leaf_vein_archer.lua` 的 `load_encyclopedia_images` / `hook_splicing_for_encyclopedia` / `inject_encyclopedia`。
- 图像分三档，别混用（用户明确纠正过）：小缩略图 86x82（`encyclopedia_tower_thumbs_*`，encyclopedia 组）；小详情图 82x82（`info_portraits_*`，战斗内选中信息条头像，game_gui 槽 68x68，模板 `info.portrait` 字段）；百科右侧大图 260x250（`encyclopedia_towers_*`，**在 encyclopedia_creeps 组不在 encyclopedia 组**，screen_map 里再乘 scale 0.7/0.708 显示）。大图源尺寸不必正好 260x250（如 260x239 用 scale 1 即可），宽对齐 260 就不糊。
- 查"某图在图集里多大/哪一帧"：`.workbuddy/read_atlas_frame.py <atlas.luac> <帧名...>`（`--list` 列全部帧名）——ctypes 调 lua51.dll 执行编译图集 luac，兼容压缩格式（根表 {count,keys,values}，帧={f_quad(4),a_size(2),trim(2),ref_scale,size(2),alias}，见 scripts/compile_image_atlas.lua）。坑：每个用到的 lua_* 函数都必须声明 argtypes 且 luaL_newstate 设 restype=c_void_p，漏了指针截断直接 OverflowError；中文路径用 luaL_loadbuffer 不用 loadfilex。判断两张纹理页是否可合并：逐帧按 f_quad 裁区域像素比对，全部一致才安全换 a_name。
- ⭐⭐ **塔菜单按钮图标显示尺寸（自定义技能/建造图标异常大必看）**（2026-10-06 leaf_vein_archer 实证）：
  `all-desktop/game_gui.lua` 的 `TowerMenuButton`/`CriketMenuButton` 共用 `tower_menu_button_size_map`：
  `tw_upgrade` 边框=`main_icons_0000`（**82×74**）、`upgrade_power` 边框=`special_icons_0000`（**82×76**），target=v(44,42)。
  分支规则（game_gui.lua:7810/9311）：**图标声明 `size` == 边框 size** ⇒ 当"原生图标"**原尺寸铺满按钮不缩放**；
  **≠ 边框 size** ⇒ 走自适应：`GU.measure_sprite_content` 量可见内容 → 缩放到 44×42 居中（边框 bo 后绘制遮住溢出）。
  ⇒ **自定义图标声明 size 千万别照抄图集像素 82×76**（会被当原生图标撑满整个按钮、被金属圈裁掉），
  要声明成 ≠82×76/82×74 的值（推荐 44×42）强制走自适应分支；圣核塔正常正因其声明 58×56/56×56。
  建造图标 `leaf_build_icon` 55×55 ≠ 82×74 所以一直正常。PNG 不用重导，改图集描述 lua 的 `size` 即可（f_quad/a_size 照旧）。
  验证：改完用 lua51.dll harness loadbuffer 该 atlas lua 确认语法+取值（mods 图集是明文 .lua，非字节码）。

- ⭐⭐ **局内 sprite 显示尺寸公式**（想调"某个单位在游戏里多大"必看）：`all/render_utils.lua:461-504` ⇒
  **最终显示像素 = 帧图集的 `size`（整幅 canvas，非 trim 后的可见内容）× `sprite.scale` × `ref_scale`**；
  局内（战斗/关卡）`ref_scale` 默认 **1**（`all/systems/render.lua:174`，只有 UI 切图 `gg_views` 才另算）。
  ⇒ **改大小只需改 `render.sprites[n].scale`**，与 `trim`/`f_quad`（只决定从图集哪块裁）**无关**。
  ⚠ `sprite.offset` 是**世界像素偏移**（`render_utils.lua:571-572` 里 `x = f.pos.x + f.offset.x`），
  **在 scale 之后加、不随 scale 缩放** ⇒ 缩小一个单位后，若挂件（血条/近战槽/点击框）显得飘，直接微调它们各自的 offset 即可，别去乘 scale。
  ⚠ **两个单位"看起来一样大"≠ scale 值相同**：若两者帧 canvas size 不同（如 192 vs 202，约差 5%），
  等比口径下 scale 相同但显示尺寸差几百分点；要**逐像素一致**得 `scale_自身 = scale_参照 × size_参照 / size_自身`。
  ⭐ 本项目【英雄】统一口径 = 等比 `sprite_scale = 0.67`（与 `ember_hero` 相同）+ 通用布局
  `anchor=(0.5,0.17)` / `offset=(0,-5)` / `health_bar.offset=(0,46)` / `melee_slot_offset=(12,0)` / `mod_offset=(0,15)` / `click_rect=(-15,-5,30,40)`。
  ⚠ 改缩放后**记得同步探针里写死的旧 scale 断言**（否则假红，见 `kr-dove-offline-lua-harness`）。

- ⭐⭐ **给单位/特效改缩放时的三个坑**（2026-10-03 Zezitra 特效缩小实证）：
  1. **`sprite` 组件默认 `scale = nil`**（`all/components.lua` `E:register_c("sprite")`，**不是 `v(1,1)`**，
     渲染时才把 nil 当 1）⇒ 探针断言"该模板未被改动"要用 **`scale == nil`**（或恰为 v(1,1)），
     **别写 `scale.x == 1`** —— 会假红。
  2. **跟随类 modifier 不碰 scale**：`scripts.mod_track_target.insert/update`
     （`all/scripts.lua:5538/5568`）只重写 `sprite.flip_x` 与 **`sprite.offset`**（按 `unit.mod_offset` 或
     `health_bar_offset` 算），**从不写 `scale`** ⇒ 挂在单位身上的特效（护盾光环等）在模板里写死的 scale
     会稳定保持，不会被跟随逻辑覆盖。
  3. ⭐⭐ **引擎通用特效模板是全局共享的，改缩放必须另建插件私有副本**：
     如 `fx_ground_hit`（`all/templates.lua:467`，`name="ground_hit_smoke"` / `anchor.y=0.27`）
     在 Dove 有 **20+ 处引用**（KR1 `archer_towers`/`boss`/`enemies`/`game_templates`/`heroes`/`mage_towers`
     + `ember_hero` + `troll_brute`…）⇒ 直接改它会把别人的特效一起缩小。
     **做法**：插件里 `E:register_t("fx_<plugin>_ground_hit","fx")` 复制同帧名/同 anchor，只多一个
     `scale`，再把引用方（`hit_fx` 等）改指新模板。**改完顺手用探针断言"引擎原模板未被污染"**。
     同理 `fx_ray_*` / 自定义 fx：**先确认是本插件自建还是引擎共享**（`grep -rn '"模板名"'` 数引用面）。
  4. ⚠ **单位本体的"挥砍刀光/攻击轨迹"通常内建在动画帧里**（如 `hero_xxx_attack`），
     随本体 `sprites[1].scale` 一起缩，**无需单独处理** —— 别去给它找不存在的独立 fx。
  5. ⭐ 项目口径：局内**特效**缩放统一用 `balance.fx_scale`（Zezitra = 0.67，与英雄本体同比例），
     改一处即可全插件生效；特效与本体同比例最协调（特写镜头下"特效过大"就是没同比例缩）。

- ⭐⭐ **射线/光束类弹丸的 `image_width` 必须 == 图集帧 canvas 宽 `size[1]`**（2026-10-03 Zezitra 实证）：
  这类脚本（`scripts.ray_*`）用 `s.scale.x = dist / image_width` 把贴图**横向拉伸到落点**，
  而 **Dove 实际绘制长 = `size[1]` × scale.x**（`all/render_utils.lua:572` 锚点也用
  `f.anchor.x * ss.size[1] - ss.trim[1]`）。
  ⇒ **`image_width ≠ size[1]` 时射线按 `size[1]/image_width` 倍拉长**，
  症状 = **"攻击距离越远，射线终点越过命中爆炸的位置越多"**（累积误差，近战距离看不出来）。
  ⚠⚠ **根因多半是"重排打包图集"**：`size = f_quad宽 + trim左右`，打包 padding 策略一变 canvas 就变，
  而 `image_width` 是从 KR1 抄来的旧值 ⇒ **凡从 KR1 抄的尺寸类常量（`image_width` /
  `line_image_width` / 依赖贴图尺寸的 offset）都必须按 Dove 实际帧 `size` 复核**。
  案例：Zezitra `ray_zezitra` `238 → 366`（KR1 原贴图 238，插件重排后帧 size=366）。
  ⭐ 探针写法：**别写死数字**，从插件图集描述文件读 `['<代表帧>']` 块的 `size[1]` 再和
  `template.image_width` 比（正则要 `\n\t\tsize = { ` 以避开 `a_size`）。

## ⭐⭐ Dove 相对 KR1 的「回归性改动」清单（移植原版机制时必查）

**背景**：Dove 是 KR1 重制版的二次开发。**若把 KR1 的机制 1:1 搬到 Dove，必须逐条确认 Dove 侧的引擎函数
没被改过**——下面的改动都是"KR1 有、Dove 没有"，直接照搬会崩或静默失效（2026-10-03 由 Zezitra 蛊惑宠物 + 护盾两 bug 实证）。
排查手法：`.workbuddy/ljdv2/luajit-decompiler-v2.exe` 反编译 KR1 的 `all/utils.lua` / `all/scripts.lua`，
与 Dove 同名文件**逐函数对照**（不变量在 KR1 有守卫/前置条件，Dove 删了 ⇒ 就是它）。

| 函数 | KR1 | Dove | 照搬后果 |
|---|---|---|---|
| `scripts.enemy_basic.insert` | `if this.enemy or this.soldier and this.soldier.moving then P:next_entity_node(this,...) end`（**有守卫**） | `all/scripts.lua:870-871` **无条件** `P:next_entity_node(this,...)` | `E:clone_entity(敌人)` 出的克隆体 `nav_path=nil` ⇒ 崩 `path_db.lua:604 attempt to index local 'n'` |
| `scripts.enemy_mixed.update` | 有 `elseif this.soldier and this.soldier.pet then` 分支（**宠物行为内建在敌人脚本**） | **该分支被删**（grep `soldier.pet` 无果） | 克隆出的宠物不会跟随/攻击（静默无效，不报错） |
| `U.find_soldiers_in_range` | `all/utils.lua:641` 带**前置条件 `v.soldier`**（只挑真士兵/英雄） | `all/utils.lua:1189` **删掉了 `v.soldier`** | 敌人（`vis.flags=F_ENEMY`，只要不撞 `F_RANGED\|F_MOD`/`F_FLYING`）被当友军 ⇒ **护盾/增益套到敌人身上** |
| **信息条取数函数返回的字段名** | KR1 用 `damage_min_ranged` / `damage_max_ranged` / `damage_icon_ranged`，**且不返回 `cooldown`** | `all-desktop/game_gui.lua:3165-3178`（`STATS_TYPE_SOLDIER`）读 **`cooldown` / `ranged_damage_min` / `ranged_damage_max` / `ranged_cooldown`** | **面板只显示近战伤害**，近战 CD 与远程伤害/CD 全空（`GU.damage_value_and_cooldown_desc(min,max,nil)` 返回 `None`；`all/gui_utils.lua:122`） |
| **敌人的 `nav_rally`** | KR1 里敌我单位**都有** `nav_rally`（KR1 的 `soldier.pet` 分支直接写 `this.nav_rally.center`） | **Dove 的敌人模板没有 `nav_rally`**（离线实测：60 个带 `death_spawns` 的敌人，其子模板 59 个 `nav_rally=nil`、只有 `nav_path`） | 照搬 KR1 的 `death_spawns` 摆位代码 ⇒ 给**敌人子体**写 `s.nav_rally.center` ⇒ `attempt to index field 'nav_rally' (a nil value)`（2026-10-14 ilor_final 真机崩）|

⭐ **摆位置要按"实体实际有什么"分支**（`hero_zezitra.place_death_spawn` 的写法，推荐照抄）：
```lua
if s.nav_rally and spread then            -- 士兵类：环绕 ±7px（原 KR1 口径）
    s.nav_rally.center = V.v(x, y); s.nav_rally.pos = V.vclone(s.nav_rally.center)
elseif s.nav_path then                    -- 敌人：按路径节点（口径同引擎 SU.do_death_spawns）
    s.nav_path.pi, s.nav_path.spi = pi, km.zmod(spi + i, 3)
    -- spread_nodes 算法：ni + spread*-2*floor(i/3) + spread
end
```
⚠ 引擎 `SU.do_death_spawns` **读 `this.nav_path`**（它写给敌人）⇒ **宠物是士兵、没有 nav_path，不能直接委托它** ✗；
宠物侧要用 `P:nearest_nodes(this.pos, ..., NF_RALLY)` 自己算节点（并对 `P:is_node_valid` 做 pcall fail-open，
离线/无关卡时会报错）。

- ⭐⭐ **插件里用 `P` / `GR` 必须自己 require**（2026-10-04 `hero_zezitra` 真机崩
  `attempt to index global 'P' (a nil value)`）：`plugin/plugin_globals.lua` 注入插件的全局只有
  `E` / `U` / `SU` / `km` / `bit` / `band` / `bor` / `bnot` / `V` / `SH` / `storage` / `UPGR` / `signal` /
  `copy` / `clone` / `RT` / `AC` / `CC` / `T` / `create_entity` / `fts` / `d2r` / `queue_insert` /
  `queue_remove` —— **没有 `path_db` / `grid_db`**。
  ⇒ 凡用到 `P:nearest_nodes` / `P:node_pos` / `P:is_node_valid` / `GR:find_waypoints` / `GR:cell_type`
  的地方必须 `local P = require("path_db")` / `local GR = require("grid_db")`
  （与 `all/scripts.lua:13`、`all/game.lua:15`、`boss_crocs_hero/scripts/hero_scripts.lua:4` 一致）。
  ⚠ 崩点会在**调用处**（如一个内层函数 `distribute_pets`），报错文本只说 "global 'P'"，连累整条协程。
  ⭐ 自查法：列出文件里所有 `X:method()` / `X.field` 的模块名，逐个确认"文件级 `local` 或
  plugin_globals 注入"；`plugin_globals.lua` 就是那份权威清单（别凭印象）。
- ⭐⭐ **把 `clone_entity` 改成 `create_entity` 时必须自己补初值**（2026-10-04 `hero_zezitra` 真机崩
  `attempt to compare number with nil`）：原版常用 `E:clone_entity(敌人)`（= 整表深拷贝，
  `all/entity_db.lua:397`）⇒ 拿到的实体**每个组件都已是运行值**；改成 `E:create_entity` 后，
  "原版默认就已存在的东西"全都要重新补。已知必补项：
  - **`health.hp` 组件默认就是 `nil`**（`all/components.lua:27`），引擎靠**插入时**的
    `health:on_insert_unconditional` 才补（`all/systems/health.lua:575-579`：`if not hp then hp = hp_max`）；
    而 `queue_insert()` 是**异步**的 ⇒ 插入队列被处理**之前**（包括同帧紧接着的下一行）读
    `e.health.hp` 就是 `compare number with nil`。**写法**：建完就走一行
    `x.health.hp = x.health.hp_max`（与引擎同口径、幂等）。
  - 外观 / `melee.attacks` / `timed_attacks` / `auras` / `unit.*` 同理逐项过一遍。
  ⭐ 通用判据：**原版那段代码"能跑"，往往是因为它操作的对象是由 clone 带来的；换构造方式 = 换契约。**

**修复范式**：一律**不改引擎**，在插件侧补回语义。

### ⭐⭐ 参照实现：「敌 → 友」转换在 Dove 的现成成品 —— `我的插件/Chen`（`holy_persuasion` 神圣劝服）

**同款机制**（策反敌人 → 变成自己人、护在身边），是 Dove 侧另一份**跑得通**的实现，
路径：`<工作区>\..\我的插件\Chen`（即 `C:\Users\29140\Desktop\我的插件\Chen`，工作区外的外部成品，`scripts/chen_scripts.lua`，主函数
`create_servant_from_enemy` / `scripts.soldier_chen_servant.update`）。
改造这类机制前**先翻它一遍**，能省几轮真机迭代。可直接借用的点：

| 主题 | Chen 的做法 |
|---|---|
| 造仆从 | `E:create_entity(attack.servant_template or "soldier_chen_servant")`（模板派生自 `soldier_paladin`） |
| **血量** | `max(70, 敌人 hp_max × health_factor)`，**并显式 `hp = hp_max`**（factor 是面板项 1.35/1.65/2） |
| **护甲** | 从敌人拷 `raw_armor` / `raw_magic_armor` + `SU.update_armor` / `SU.update_magic_armor` |
| 敌人 hp_max 可能是**数组** | `max_health_value()` 取表内最大值（离线实测确有这种敌人） |
| 外观 | 拷 `sprites[1]`（**只单层** —— 我们已改成逐层，比它强），并 `safe_walk_angles` /
  `safe_visual_animation_name` 校验动画名、`hidden=false`、清 `idle_flip.animations` |
| 攻击 | 从敌人提取伤害再按 `attack_factor` 缩放；`ranged`/`timed_attacks`/`timed_actions` 各自
  normalize，并**过滤"不安全法术"**（`unsafe_spell_name` / `has_unsafe_spell_fields` 等） |
| insert | 委托 `scripts.soldier_barrack.insert`（引擎标准士兵初始化） |
| AI | **自写士兵循环**：每帧重算 `servant_guard_pos` → block 管理 → timed_actions → timed_attacks →
  spell → ranged → melee → `go_back_step` → idle+regen，**末尾 `coroutine.yield()`** |
| **站位** | `servant_rally_pos`：以 owner 为圆心按槽位环形（`follow_radius` 42，y 压 0.55）；
  敌人进入 `chase_radius`(110) 且处于 owner `guard_radius`(170) 的"牵引半径"内才去追 |
| 目标筛选 | 排除 boss / 特殊路径态 / `hp_max > hp_limit`（900/2200/99999），再按 score 排序 |
| **block 清理** | `release_servant_block`（`U.unblock_target` + 清 `enemy.blockers` 悬空 id）、
  `prune_servant_block_refs`、`servant_can_hard_block_enemy` |

### ⭐⭐ 把敌人的「攻击」整套搬过来：先数清有几个通道（2026-10-04 `hero_zezitra` 实证）

"友军沿用敌人的攻击"这件事**不止一个通道**，漏一条那类敌人就等于没攻击。离线数一遍（380 个敌人模板）：

| 通道 | 有该通道的敌人数 | 搬不搬 | 备注 |
|---|---|---|---|
| `melee.attacks` | 311 | ✅ 搬 | 记得给每条清 `F_ENEMY`、补 `F_BLOCK`，并重算 `melee.order` |
| `ranged.attacks`（`attacks[i].bullet`） | **67** | ✅ 搬 | ⭐ **最易漏**：其中 **41 个敌人"只有远程、没有 timed_attacks"** ⇒ 不搬就完全没攻击。搬完**必须重算 `ranged.order`**（组件默认 `{1}`，第 2 招会被漏） |
| `timed_attacks.list` | 82（91 条条目） | ❌ **不搬、更不要跑** | ⚠⚠ **上一版这里写错了，2026-10-04 真机崩后纠正**：引擎的士兵通道 `SU.y_soldier_do_timed_attack`（`all/script_utils.lua:1883`）是 **`spell` 型专用**（`E:create_entity(attack.spell)` + `attack.cast_time`，且先算 `a.min_range`）；而敌人条目 **spell 型 = 0 条 / 91**、**61 条连 `min_range` 都没有**，type 多为 `custom`（**依赖敌人自己的脚本**）⇒ 硬跑必崩 `all/seek.lua:777 arithmetic on local 'min_range'`。**结论：敌人的"特殊技"无法跨单位沿用**，友军只沿用 **近战 + 远程** |
| `timed_actions.list` | **4** | ❌ **不搬** | 那是**召唤单位**语义（`entity` / `entity_names` 字段，如 `enemy_necromancer` 召骷髅）⇒ 搬过来会让宠物召唤**敌对**单位 |

**拷贝时的四件事**（缺一件就崩或静默失效）：

0. ⭐ **显式清空"技能通道"**（2026-10-04 用户要求"被蛊惑的单位不使用技能"）：
   除了"少拷"，落地时再补
   ```lua
   if e.timed_attacks then e.timed_attacks.list = {} end
   if e.timed_actions then e.timed_actions.list = {} end
   ```
   把"友军只用普通近战/远程"这条约束**写进代码**。
   ⚠ 原版 KR1 的脚本里**没有**任何 `disabled = true` 之类的显式禁用 —— 它是靠"宠物跑士兵分支 +
   敌人技能条目本来就不适配士兵通道"**自然达成**的（查证过 `mod_possession_pet` / `soldier_possessed_pet`
   全文）；我们改成显式清空，语义一致、且以后有人想拷回来会被挡住。
   ⚠ 边界：远程攻击**弹丸自带的效果**（减速 / 范围）仍随普攻生效 —— 属"普攻口径"，不算技能。
   ⭐ **"攻击里的特殊效果"实测占比**（2026-10-04 离线统计，回答"只留普攻"这类需求时用得上）：
   敌人**近战**条目 354 条里 **141 条**带特殊字段（`mod` 命中挂状态 / `hit_fx` / `type=area`+`damage_radius` 范围近战，
   如 `enemy_crystal_golem`）；**远程**条目 68 条只有 1 条带特殊字段（基本干净）；
   但**远程弹丸模板 62 个里 60 个自带 `main_script.update`** ⇒ 弹丸行为（范围/减速/特殊）是挂在**弹丸模板**上的，
   受弹丸名控制、不只是攻击条目。⇒ 要"彻底纯化普攻"就得连弹丸一起换，**会改变伤害形态，需先跟用户确认**。

1. **过滤坏引用**：原版攻击条目里确实有 `bullet = ""`（`enemy_necromancer_kr6`）或在 Dove
   **解析不出的模板名** —— 照搬会在友军开火时 `E:create_entity("")` 崩。
   ⇒ 逐条检查 `bullet` / `entity` / `entity2` / `mod` / `spell`：**nil 合法**，空串或 `E.entities[ref] == nil` ⇒ **丢弃该条攻击**。
2. **别"顺手"把敌人条目塞进引擎的士兵/友军处理函数**：每个引擎通道都有**自己的条目形态契约**
   （例：士兵 `timed_attacks` 通道只认 `spell` 型；`selfdestruct` 要 `hit_time`/`damage_radius`）。
   把敌人条目直接喂进去 ⇒ 多半是 **nil 参与算术** 的崩（如 `min_range`）或空引用 `create_entity(nil)`。
   ⇒ 挪进陌生通道前，**先读那个 `do_*` 实现**，列出它读哪些字段、缺了会怎样。
3. **别翻 flag 也别不翻**：敌人远程攻击与其弹丸的 `vis_bans` 通常就是 **0**（引擎靠
   `find_enemies_in_range` / `find_soldiers_in_range` 选边）⇒ 原样拷即可；但**近战**要补 `F_BLOCK`
   并清 `F_ENEMY`（原版做法）。判据 = **看那个字段在引擎里被谁读**，别凭"敌人/友军"猜。

### ⚠⚠ 「有一整套模板 + 脚本」≠「这个机制真的在生效」：把数值代进公式手算一遍

2026-10-04 `hero_zezitra` 实证：宠物挂的退化光环 `aura_possessed_pet_degeneration`
（模板 + 脚本**都齐全**、名字就叫 degeneration）—— 但它的
`factor_start = factor_end = 0`（**原版就是这个值**）⇒ 每 2 秒扣 `最大生命 × 0 = 0` 血 ⇒ **空转**：
既不扣血也不治疗（唯一的"托底"分支还被外层 `hp >= 10%` 守卫挡死）。
⇒ 结论："宠物随时间掉血"是**误读**；我此前照抄上一版文档写错了，后来靠"手算"才发现。

**通用判据**：看到"某模板/光环/字段暗示有某个机制"时，别信名字，**把值代进公式算一遍**；
尤其注意 **乘法型因子为 0/nil**、**守卫条件互相排斥**（外层要求 `x >= a`、内层却只在 `x < a` 时生效）这两种
"写着却永不触发"的形态。这类错误**不报错、只静默失效**，只有手算/实测才能发现。

### ⭐⭐ 「沿用敌人的攻击条目」必须做"友军化翻译"（2026-10-04 `hero_zezitra` 两连崩实证）

把敌人的 `melee.attacks` / `ranged.attacks` 直接深拷贝给友军**不够** —— 敌人形态的条目有两类坑，
且都**只在开火那一刻**才炸：

| 坑 | 实测占比 | 崩点 | 修法 |
|---|---|---|---|
| **缺 `cooldown`**（射速写在组件级 `ranged.cooldown`） | 4/68 条远程 | `soldier_pick_ranged_target_and_attack`（`all/script_utils.lua:1734`）算 `a.cooldown × unit.cooldown_factor` | 缺就回落 `ranged.cooldown` → 再回落 1 |
| **带敌人专用回调 `side_effect`**（回调里读 `this.enemy`） | 3/354 条近战 | `y_soldier_do_single_melee_attack`（`:2391`）命中后调 `attack.side_effect(this, store, d, target)`；`kr1/enemies.lua:612` 读 `this.enemy.can_do_magic` | **剥掉 `side_effect`**（顺带补 `F_BLOCK`/清 `F_ENEMY`/补音效） |
| **引用坏模板**（`bullet = ""` / 解析不出的名字） | 1/76 条远程 | 开火时 `E:create_entity(a.bullet)` → `quickcopy(nil)` | 按字段逐查"存在性"，坏条目直接丢 |
| **模板自带占位攻击**（见下，与"拷敌人"无关但同类崩） | 模板级 | 同上 `:1734` | 置 `disabled` + 数值兜底 |

### ⭐⭐ 「模板自带占位攻击」是个独立的坑（2026-10-08 `hero_zezitra` 真机崩）

派生士兵模板时，只要基模板带 `ranged` 组件，就会继承一条 **`CC("bullet_attack")` 占位攻击**，
而 `bullet_attack.cooldown` 的**组件默认值就是 `nil`**（`all/components.lua:580`；`max_range/min_range/ts = 0`）。
*只把 `bullet` 置 nil 是不够的*（`tt.ranged.attacks[1].bullet = nil` 这种写法很常见）——
只要单位**有机会走到远程取招循环**（`this.ranged` 存在且 `ranged.order` 指着它，默认 `{1}`），
`a.cooldown * unit.cooldown_factor` 就是
`attempt to perform arithmetic on field 'cooldown' (a nil value)`。
⚠ 它**极难触发**（`max_range = 0` ⇒ `dist2 <= 0`，只有"敌人与单位坐标完全相同"才命中 ——
同波同节点堆叠刷怪时才出现），所以表现为**偶发**，很容易被当成玄学。

**正确姿势**：
```lua
-- 没有可用远程时：保留那一条（别清空！order 默认 {1}，空了会在 `a.disabled` 处索引 nil；
--                 而且 all/game.lua:1117 等处有 ranged.attacks[1] 的裸读）
ph = e.ranged.attacks[1]
ph.disabled = true                        -- 取招循环 `if a.disabled then` 会跳过 ⇒ 不崩也不开火
ph.cooldown, ph.chance, ph.ts = 1, 1, 0   -- 数值兜底：万一被重新启用也不会 nil 运算
ph.min_range, ph.max_range = 0, 0
e.ranged.order = { 1 }
```
⇒ **通用结论**：给"改造成友军/宠物"的模板加远程能力时，**一律整表重建** `ranged.attacks`
（有就归一化拷贝、没有就 disable 占位），别只在模板上打 `bullet = nil` 补丁。
**近战侧没有这个坑**（`melee.attacks[1]` 是实打实的普攻，不是占位）。

### ⭐⭐ 清空 `timed_attacks.list` 会让"选中该单位"直接崩（2026-10-08 `hero_zezitra` 真机崩）

把单位改造成"不用任何技能"时，最直觉的写法是 `e.timed_attacks.list = {}` —— **这是坑**：
`all-desktop/game_gui.lua:779`（选中单位时画射程圈）写的是

```lua
elseif e.timed_attacks and e.timed_attacks.list[1].max_range and not e.timed_attacks.list[1].disabled then
```

**只守了 `e.timed_attacks`，`list[1]` 没守卫** ⇒ 空表 ⇒ `attempt to index a nil value`，
而且**只有玩家点选这个单位时才崩**（平时不触发，很难联想到）。同理 `ranged.attacks[1]` 在同一段里也是裸索引。

⚠ 也**不能把 `timed_attacks` 整个置 nil**：`SU.y_soldier_timed_attacks`（`all/script_utils.lua:1936`）
对 `this.timed_attacks.list` 同样无守卫。⇒ **正解 = 留一条 `disabled = true` 的占位条目**：

```lua
-- 保留/补一条占位；禁用 + 抹掉能触发的引用 + 数值字段补 0
ph.disabled = true
ph.bullet, ph.mod, ph.spell, ph.power_name, ph.fn_can = nil, nil, nil, nil, nil
ph.cooldown, ph.ts, ph.min_range, ph.max_range = 0, 0, 0, 0
```
消费者见 `disabled` 都会跳过（`ipairs` 里 `a.disabled or ...` 短路，不会再碰数值字段）✓。

**排查口令**：症状是"**点选某单位就崩**在 `game_gui.lua` 的 update 里、`attempt to index a nil value`"
⇒ 去看该单位的 `ranged.attacks` / `timed_attacks.list` **是不是空表**（空表比 nil 更阴险）。
扫全库同类无守卫读：`grep -rn "\.timed_attacks\|\.ranged\.attacks\[1\]" --include=*.lua all/ all-desktop/`
然后逐个看有没有 `if e.xxx then` 同层守卫。

⭐ **做法**：把"翻译"抽成**可离线单测的 helper**（`sanitize_ranged_attack(a, ranged_comp)` /
`sanitize_melee_attack(a)`），探针里**把缺字段/带回调的假条目喂进去跑**断言 ——
比"等真机崩了再修"快得多（本次就是这么修完还能立刻证明修对了）。
⚠ 顺带的防御：`vis_flags`/`vis_bans` 可能是 nil，`U.flag_*` 会 `band(nil)` 报错 ⇒ 写 `or 0` 与 `if x and ...`。

### ⭐⭐ 攻击自带的 `mod`/`mods`：**施加者 = 攻击者**（2026-10-08 `hero_zezitra` 真机崩）

"沿用敌人攻击"时最容易漏的一类：攻击条目上的命中效果（`a.mod` / `a.mods`）。
引擎的施加点是 `y_soldier_do_single_melee_attack`（`all/script_utils.lua:2395`）：

```lua
if attack.mod then
    local mod = E:create_entity(attack.mod)
    mod.modifier.source_id = this.id        -- ← **攻击者自己**
    ...
    simulation:queue_insert_entity(mod)
end
```

⇒ 宠物/友军用了这条攻击，`source` 就是**它自己**。而有些 mod 的脚本假设 source 是**敌人**：
`mod_lycanthropy.insert`（`all/scripts.lua:8299/8303`）读 `source.nav_path.pi/spi/ni` 与 `source.enemy.can_do_magic`
—— 士兵类实体**没有 `nav_path`、也没有 `enemy`** ⇒ 崩在 `:8299`（`attempt to index field 'nav_path'`），
且**只在命中那一刻（mod 被 insert）才炸**，表现为"狼人宠物一咬就崩"。

**判据（怎么找出该剥哪些）**：`grep -rn "source\.nav_path\|source\.enemy" --include=*.lua all/ kr1/`
（本次全库 7 处），再逐个看能不能**经由"拷来的攻击"到达**：
- 攻击 mod（如 `mod_lycanthropy`）⇒ **能** ⇒ 必须处理；
- `*_aura.update` / boss 脚本 ⇒ 拷攻击到不了 ⇒ 不用管。
⇒ 建一个**黑名单常量**（`UNSAFE_ATTACK_MODS`）+ `sanitize_*(copy)` 里剥掉；⚠ **别一刀切全剥**：
实测敌人近战 **39/397 条**带 mod（毒/燃烧/吸血/网…），那些不读 enemy 字段，剥了会丢"沿用敌人攻击"的味道。
远程同理：效果在**弹丸模板**的 `bullet.mod` 上（施加者仍是射手）⇒ 建 `bullet_mod_unsafe(tpl)` 在重建远程时跳过。
排查口令：崩在 `script_utils.lua` 的 `pick_*`/`do_*` 里、且参数是**从敌人拷来的条目** ⇒ 就是缺字段/带敌人回调。

### ⭐⭐ 攻击条目上的**函数型字段**一律剥掉（`fn_can` / `fn_filter` / `side_effect`）

2026-10-08 又一次真机崩（`kr1/game_scripts.lua:41915: attempt to compare number with nil`）：
`enemy_basic_lava` 的 `melee.attacks[2].fn_can = scripts.enemy_basic_lava.fn_can_attack_breath`，
而这个回调读 **`this.melee_start_ts`** —— 那是**敌人脚本自己每帧写的状态**（`enemy_basic_lava.update`），
宠物没有 ⇒ 引擎在 `soldier_pick_melee_attack`（`all/script_utils.lua:2633`）里
`(not a.fn_can or a.fn_can(this, store, a, target))` **以攻击者为 `this`** 一调就崩。

**关键认识：这些回调是"敌人脚本的闭包"，只要换了 `this` 就必然不可靠。**
引擎对攻击条目的回调读取点（全部把**攻击者**当 `this`）：
- `fn_can`：选招 `all/script_utils.lua:1859 / 2633 / 4048`
- `side_effect`：命中结算 `:1642 / 2390`（以及 `:4122 / 4174`）
- `fn_filter`：范围伤害筛目标 `:4140`

⇒ **做法：`sanitize_*` 里剥掉条目上「所有 `type(v) == "function"` 的字段」**（不用维护名单）：

```lua
for k, v in pairs(copy) do if type(v) == "function" then copy[k] = nil end end
```
比"逐条 nil"更稳：`Desktop/我的插件/Chen (1)`（`scripts/chen_scripts.lua:1109/1206/1327/1413`）是逐条
`fn_can = nil` / `side_effect = nil` —— **会漏掉 `fn_filter`**（`enemy_bandersnatch` 有一条）。
离线量化（`.workbuddy/scan_enemy_melee.lua` 新增"函数型字段"段）：近战条目上共 **17 个**函数字段
（`fn_can` 12 / `side_effect` 4 / `fn_filter` 1），远程/技能通道 0 个。
➕ 回归断言（探针里，**全库横扫**）：把 397+ 条敌人攻击条目逐条 `sanitize`，要求"剥后函数字段数 == 0"，
再拿 `enemy_basic_lava[2]` / `enemy_bandersnatch[1]` 两条真条目做定点回归（`fn_can` / `fn_filter` 必须为 nil）。

### ⭐⭐ **敌人通道 ≠ 士兵通道**：拷来的条目要按"士兵通道的必填字段"补契约（`loops` 坑）

紧跟着的第二次真机崩（`all/script_utils.lua:1491: bad argument #1 to 'ipairs' (table expected, got nil)`）：

引擎只要看到 `attack.loops` 有值，就走 **循环远程** 分支 `SU.y_soldier_do_loopable_ranged_attack`
（`script_utils.lua:1778` ⇒ `:1491`），而该分支**裸读**两样东西：
```lua
for i = 1, attack.loops do
    U.animation_name_facing_point(this, attack.animations[2], target.pos)   -- :1485 裸读 animations[2]
    for si, st in ipairs(attack.shoot_times) do                            -- :1491 裸读 shoot_times（ipairs）
```
而**敌人自己的通道**根本不读 `shoot_times` —— 它在循环里按 `attack.shoot_time` 出手。
⇒ 于是出现"**敌人本体跑得好好的条目，拷给宠物一开火就崩**"：
`enemy_twilight_elf_harasser[1]` 是 `loops=4 + shoot_time=0.1`、**没有 `shoot_times`**（离线实测：
敌人远程 76 条里 4 条带 `loops`，只有它缺 `shoot_times`）。

**通用结论（比"逐条事故修补"更重要）**：从敌人条目"翻译"到士兵通道时，
**要按士兵通道的必填字段补齐契约**，而不是假设"敌人能跑就行"。
本次做法（`sanitize_ranged_attack` 末尾）：
1. `loops` 有值且 `shoot_times` 不是表 ⇒ 补 `{ shoot_time }`（每个 loop 一发 ⇒ 保住 4 连发的手感）；
2. 连 `animations[2]` 都没有 ⇒ **清掉 `loops`**，回落单发路径；
3. 回落单发时补**单数** `animation`（单发函数 `y_soldier_do_ranged_attack`（`:1596`）读的是 `attack.animation`，
   缺了会 `animation ... not found`）。
➕ 探针里立个**全库不变式**：所有远程条目 sanitize 后必须满足"有 `loops` ⇒ `shoot_times` 可 `ipairs` 且
`animations[2]` 存在"，违反数为 0 —— 以后游戏数据再多一条也不会漏。

排查口令：**崩在 `ipairs`/裸字段索引、且参数是"从敌人拷来的攻击条目"⇒ 十有八九是士兵通道的必填字段没补**。

### ⭐⭐ 收口方案：**契约校验 + 标准普攻兜底**（用户 2026-10-09 定，推荐照抄）

"沿用敌人攻击"这条线一路踩了四层坑（缺数值 → `side_effect`/`mod` → `fn_*` 回调 → 通道契约）。
与其每次崩了再补，**改成"出不通过就退化成本体行为"** —— 前提是**本体得有可用的普攻**：

⚠ 先查证：我们宠物模板自带的 `melee.attacks[1]` 是**桩**（伤害 2-6、`cooldown = 900000` = 永不触发），
`ranged.attacks[1]` 也是桩（`bullet = nil`/`cooldown = nil`）⇒ **照字面"遵循本体"= 宠物不攻击** ✗。
⇒ 必须**先造一套"标准普攻"**（骨架用本体、**数值沿用敌人**）。

落地三件套：
1. **契约校验**（只管"会不会崩"，不管手感）：列出引擎在该通道**无守卫读**的字段，
   `type(...) ~= "number"` 即判不合格（近战：`hit_time`/`cooldown`/`damage_min`/`damage_max`/`damage_type`；
   远程：`bullet` 非空 + `cooldown`/`ts`/`chance`/`shoot_time`/`min_range`/`max_range` + `loops` 契约）。
2. **标准普攻**：骨架 = 本体攻击的 `deepcopy`（字段干净、无敌人机制），数值/动画/音效用敌人的
   （逐个 `pick(key, "number"|"string", fallback)`）；近战补 `F_BLOCK`；远程**不带 `loops`/`shoot_times`**（走单发路径，
   绕开循环分支的契约负担）；远程拿不到合法 `bullet` ⇒ 返回 nil（该宠物就没有远程）；最后再 `strip_attack_callbacks`。
3. **接线**：`ok ? sanitize(保留全部手感) : standard_attack_for(...)`；两处（近战拷贝、远程重建）都要接。
➕ 探针立**全库不变式**：把敌人所有近战/远程条目走一遍"该走的那条路"，断言**产出的条目 100% 通过契约校验**（违规 0）。
这样以后游戏数据再多一条、或又冒出新的敌人机制，**最多是那一招变朴素，不会崩**。

⚠ 别选"白名单重建"：引擎在士兵通道读的字段近战就有 22 个（含 `damage_radius`/`damage_flags`/`damage_bans`/
`hit_times`/`dodge_time`/`include_blocked`…），凭记忆列清单**当场就会漏**，长期维护成本高。


**⭐ 近战第二坑（2026-10-05 真机崩实证，离线量化）**：`y_soldier_do_single_melee_attack`
**开头第一句**就是 `while store.tick_ts - start_ts < attack.hit_time` ⇒ **`hit_time` 必须是数值**。
离线统计 Dove（426 敌人 / 近战 397 条）：

| 字段 | 缺失条数 | 后果 |
|---|---|---|
| **`hit_time`** | **43/397** | **`attempt to compare number with nil` 直接崩**（敌人自己的通道不读它 ⇒ 本体不崩，友军走士兵通道就崩） |
| `cooldown` | 18/397 | 不崩，但 `pick_melee_attack` 里 `cooldown = 0` ⇒ **零冷却连击** |
| `damage_type` | 1/397 | 不崩（`~= DAMAGE_NONE` 虽真但 `damage_min` 也判 false ⇒ 那条不出伤） |
| `hit_times` | 350/397 | 引擎不读（loopable 变体才用）⇒ 不用补 |
| `sound` | 305/397 | `S:queue(nil)` 安全；补个通用音更好 |

⇒ 兜底统一取"**友军模板自己的那条普攻**"当基准（`E:get_template("<entry>").melee.attacks[1]`），
别写死魔数。⚠ **引擎原生 `betray`（`SU.betray_enemy` → `enemy_betray_logic`，`all/script_utils.lua:5280`）
有同一个坑**：它直接拿敌人条目跑 `SU.y_soldier_melee_block_and_attacks` ⇒ 那 43 个敌人要是被本体策反
也会崩（别以为"本体做了就安全"）。

**⭐ 多招敌人必须重算 `melee.order`**：`soldier_pick_melee_attack` 是 `for _, i in ipairs(this.melee.order)`
取招的 ⇒ 拷了 3 条近战却留着默认 `order = {1}` ⇒ **永远只出第 1 招**（`enemy_redcap` /
`enemy_armored_nightmare` / `enemy_nine_tailed_fox` 各 3 条）。远程同理（`ranged.order`）。

**⭐ 拷多层 sprite 后，第 2+ 层要 `ignore_start = true`**：`U.animation_start` /
`U.animation_start_default` 会把**每一层**都改名成 `idle/walk/attack`，而武器层 / 坐骑层 / `*_fx`
特效层各有自己的命名体系 ⇒ 请求到不存在的动画键，真机日志刷
`render.error on_render_update() - animation xxx_idle not found`。
置 `ignore_start` 后这两个入口都会**跳过**该层（`all/utils.lua` 里 `if not a.ignore_start then`），
它保留原本的动画名继续自播 —— 与"宠物红光覆盖层"同款做法。

**⭐ "原地拦截" vs "跟随"就差一个字段**：`SU.soldier_pick_melee_target` 里
`local center = this.nav_rally and this.nav_rally.center or this.pos` —— **索敌圆心是 `nav_rally.center`**，
半径是 `this.melee.range`。所以：
- 想让单位**守在原地拦截** ⇒ 只设一次 `nav_rally.pos/center`（生成点）且**别再动它**；
- 想让它**跟随某人** ⇒ 那人每次改集结点时把它的 `center/pos` 一起改、并置 `nav_rally.new = true`。
`nav_rally.pos` 是"回位点"（`SU.soldier_go_back_step` 用），`center` 是"索敌圆心"，语义不同。

### ⭐ 死亡特效 / 自爆：优先用引擎的 `selfdestruct` 组件，别手搓

`SU.y_soldier_death`（`all/script_utils.lua:1375`）对 `this.selfdestruct` 有**完整结算**：
播 `sd.animation` → 等 `sd.hit_time` → `sd.hit_fx` 落地 → 在 `sd.damage_radius` 内向
`sd.vis_flags/vis_bans` 选出的目标做一次范围伤害（含 `sd.mod`）→ 收尾。
⇒ 想给单位加"死亡自爆"，**只需在模板上 `add_comps("selfdestruct")` + 填字段**：

```lua
tt.selfdestruct.damage_min/damage_max/damage_radius = ...
tt.selfdestruct.damage_type  = DAMAGE_PHYSICAL
tt.selfdestruct.animation    = "death"        -- ⚠ 见下
tt.selfdestruct.hit_time     = fts(20)
tt.selfdestruct.hit_fx       = "fx_xxx"       -- 得是真实存在的 fx 模板
tt.selfdestruct.sound        = "BombExplosionSound"  -- ⚠ 见下
```
- ⚠ **`animation` 不能用 `"selfdestruct"`/`"suicide"` 当贴图是"别人"的**：`selfdestruct` 组件的默认动画名
  就是 `"selfdestruct"`，但只有原版那几个自爆单位有该帧；如果单位贴图是**沿用敌人**的（敌→友转换），
  只能用每个单位都有的 **`"death"`**（引擎模板也有先用例：`kr1/heroes.lua:20507`）。
- ⚠ **音效要选"常规关卡一定会加载的声音组"里的**：用 `BombExplosionSound`
  （`kr1/enemies.lua:648` 就有敌人拿它当死亡音）这类通用音，别用自定义/关卡特有音
  （否则 `SOUND X ... sound sources missing`）。`S:queue(nil)` 是**安全**的（开头就 `if not id then return end`）。
- 组件默认 `damage_type = DAMAGE_PHYSICAL`、`vis_flags = F_RANGED`、`vis_bans = 0`；
  击杀伤害类型是 `DAMAGE_EAT/HOST/DISINTEGRATE` 时**不触发**自爆（引擎行为，别当 bug）。
- ⭐ **要"伤害随技能等级"就只能在建实体时逐只写**（模板只存一份值）：
  `e.selfdestruct.damage_min/max = <按技能等级取数组>`，模板里留**最高档**做兜底；
  抽个可单测 helper（如 `explode_damage_for(skill_level)`，内部 clamp 到数组长度）。
  ⚠ 伤害类型若要用 `DAMAGE_MAGICAL_EXPLOSION`（32，`all/constants.lua:113`）—— 它是**伤害类型**枚举，
  与 `F_BOSS/F_MINIBOSS`（也是 32，但属 **flag 位**枚举）**不同命名空间**，别混。
- 引擎自爆伤害取 `sd.damage or math.random(sd.damage_min, sd.damage_max)` ⇒ 组件 `damage = nil`（默认）才会用 min/max。

### ⭐⭐ 把某个 balance 值"标量 → 按等级数组"是一次**跨文件重构**（2026-10-08 `hero_zezitra` 真机崩）

`wormtongue.cooldown` 从标量 `25` 改成数组 `{25,22,20}` 后，**只改了 balance / config / 面板 / 文案**，
漏了**模板把整表写进条目**这一跳：

```lua
tt.timed_attacks.list[2].cooldown = B.skills.wormtongue.cooldown   -- ← 现在是个 table！
```
⇒ 主循环 `store.tick_ts - a.ts >= a.cooldown` 直接 `attempt to compare table with number`（崩）。

**排查套路（改完数组一定要跑）**：
```bash
grep -rn "\.<字段名> = " scripts/hero_templates.lua scripts/hero_scripts.lua   # 逐条看右侧是不是整表赋值
```
凡"会被引擎**做算术/比较**的字段"（`cooldown` / `damage` / `max_count` / `range` / `hp_max`…）
**在实体/条目上必须落成数值**；数组只能活在 `balance` 与"技能表"这类**由代码按等级索引**的地方。

✅ 正确姿势（三件套，缺一就崩或静默失效）：
1. **模板**：条目字段写**数值兜底**（取数组第 1 档，并兼容"配置还是标量"的老情况）；
2. **`level_up`**：按当前技能等级把数值写回条目（`a.cooldown = s.cooldown and s.cooldown[sl] or 25`）；
3. **模板技能表**：把数组挂到 `tt.hero.skills.<技能>.cooldown`（**level_up 要从这儿取**；
   只挂 `pets_max` 之类、忘了挂 cooldown ⇒ 上面那行会索引 nil）。
➕ 回归守卫：探针里断言 **`type(条目的 cooldown) == "number"`**（模板层）+ 每档数值（运行层），
这样"再把数组塞回去"会立刻红。

### ⭐⭐ "一次操作影响多个目标"（一次抓多只 / 一次上多个 debuff）：**派生同款 mod 实例**

2026-10-08 `hero_zezitra`："一次施法最多策反两只"。**别手写第二套协程** —— 正确姿势是
**给每个额外目标各建一个同款 mod 实体**，让引擎替你把协程跑起来：

```lua
local mod = E:create_entity(entry.mod)          -- 与攻击通道同一套字段（照 all/script_utils.lua:2395 抄）
mod.modifier.ts = store.tick_ts
mod.modifier.target_id = target.id
mod.modifier.source_id = hero.id
mod.modifier.level = entry.level
mod.modifier.damage_factor = hero.unit.damage_factor
mod.extra = true                                -- ⭐ 自标"派生体"
queue_insert(store, mod)
```
- 每个实例自带完整生命周期（生效 → 守护 → 收尾），**一个都不会漏**（本次是"宠物死亡爆炸/被顶替复活"这些收尾）。
- ⚠ **派生体必须自标记并据此跳过"只该做一次"的事**：本次是"**不写 CD、不再派生**"
  （否则两个实例会互相覆盖 CD、甚至指数级派生）。主实例负责按"本次实际影响了几只"统一收尾。
- 目标挑选：复用主通道**同一套**筛选（同一个 `detect_foremost_*_filter_on` + 同一个 `fn_can` 回调），
  用一个 `picked` 表排除主目标与已选的，别另写一套规则。

### ⭐⭐ 容量上限别用 `#list` + `==`（"延迟移除"的集合 + 一次插多个）

同一次的另一个真机现象：**"同时持有上限"表现成 4 只**。旧写法

```lua
if pa.pets and #pa.pets == pa.pets_max then pa.pets[1].replaced = true end   -- ← 只**标记**
table.insert(pa.pets, e)                                                    -- ← 标记的那只还在表里
```
两处都不成立：① 被标记 `replaced` 的对象**要等它自己的协程下一拍**才 `table.remove` ⇒ 列表长度**立刻超上限**；
② "一次插多个"时第 2 次插入 `#list` 已经 ≠ 上限 ⇒ **顶替根本不触发**，能一路涨到 4、5…

✅ 正确姿势：**按"有效元素个数"算容量**（跳过"待移除 / 已死"的），再把**最老的**若干个标记掉直到装得下：
```lua
local live = {}                    -- 只数还活着的（not replaced and not health.dead）
for i = 1, #pets do local p = pets[i]; if p and not p.replaced and not (p.health and p.health.dead) then live[#live+1]=p end end
for i = 1, #live + 1 - cap do if live[i] then live[i].replaced = true end end   -- 从最老的开始腾位置
table.insert(pets, e)
```
➕ 别忘了**每条"离开"的路径都要摘表**（本次死亡分支原本没摘 ⇒ 死宠长期占长度，让 `==` 判断进一步失效）。

### ⭐⭐ 挂在单位身上的 mod「视觉残留」：自带 teardown + `remove` 所有权守卫（2026-10-04 `hero_zezitra` 护盾实证）

护盾/光环这类"挂在目标身上的 mod"，视觉常是 **mod 实体自己的 `render.sprites`**（靠
`scripts.mod_track_target.update` 每帧把 `this.pos` 贴到目标上）。当"护盾看起来还在、其实已经失效"时，
排查与修法如下：

- **静态结论**：`mod_track_target.update`（`all/scripts.lua:5574`）本身**是带到期判断的**
  （`m.duration >= 0 and store.tick_ts - m.ts > m.duration`），`render` 系统的
  `on_remove_unconditional` 也会把所有 sprite 标 `marked_to_remove` ⇒ **正常路径下"实体没了贴图一定没"**。
  所以"残留"99% 意味着**实体压根没被移除**（而不是移除后贴图没清）。
- **兜底修法（按症状，别赌路径）**：给 mod 写**自己的 `main_script.update`**（照抄 `mod_track_target` 的
  跟随 + offset 逻辑），把到期判断变成**本协程显式 deadline**，并让**所有出口**都走一个
  `teardown(this, store)`：
  ```lua
  function scripts.<x>.teardown(this, store)
      if this.render and this.render.sprites then
          for i = 1, #this.render.sprites do
              this.render.sprites[i].hidden = true
              this.render.sprites[i].marked_to_remove = true
          end
      end
      queue_remove(store, this)          -- plugin_globals：= simulation:queue_remove_entity
  end
  ```
  `on_damage` 里"打碎/被无视护盾击碎"那两条路也要改走 `teardown`（原版是裸 `queue_remove`）。
- ⭐⭐ **`remove` 必须加所有权守卫 + 还原"我接手前的 `on_damage`"**：护盾靠
  `target.health.on_damage = 护盾处理` 接管受击，原版 `remove` 一律 `target.health.on_damage = nil` ——
  **若目标本来就有自己的 `on_damage`（宠物 = `soldier_possessed_pet.on_damage`）就被清掉了**；
  多面盾先后失效时旧盾还会把新盾的处理清掉。正确写法：
  ```lua
  -- insert：this._prev_on_damage = target.health.on_damage；然后才接管
  -- remove：if target._shield_mod == this then
  --             target._shield_mod = nil
  --             if target.health.on_damage == <本护盾处理> then
  --                 target.health.on_damage = this._prev_on_damage end
  --         end
  ```
- ⚠ 若"残留"仍复现，**先取三条信息再动手**：留在谁身上（英雄/友军/宠物）、是"到期留"还是"打碎后留"、
  日志里有没有 `remove <模板名> aborted`（`simulation:remove_entity` 里某 system `on_remove` 返回 false 会打）。



### ⭐ 禁止"策反/控制 boss"：`F_MINIBOSS` 就是 `F_BOSS`（同位），要写在攻击的 `vis_bans` 上

2026-10-04 `hero_zezitra`（禁止蛊惑 boss/小 boss）查证：
- **`all/constants.lua:294-296`：`F_BOSS = 32`，`F_MINIBOSS = F_BOSS`**（同一个位；`-- F_MINIBOSS = 64` 是注释掉的旧设想）
  ⇒ 写 `bor(F_FLYING, F_BOSS)` 与 `bor(F_FLYING, F_BOSS, F_MINIBOSS)` **语义等价**，后者只是把意图留在代码里 + 未来防错。
- **`vis_bans` 是"目标不能有的 flag"**，而**引擎真的会拿它过滤**：
  `SU.soldier_pick_melee_attack`（`all/script_utils.lua:2633`）选招式时判
  `band(a.vis_flags, target.vis.bans) == 0 and band(a.vis_bans, target.vis.flags) == 0`
  ⇒ 带 `F_BOSS` 的敌人**选不到**那条攻击（所以 boss 根本吃不到"策反一击"）。
  ⚠ 注意：**近战选"目标"时不看某条攻击的 `vis_bans`**（`soldier_pick_melee_target` 只看 `F_BLOCK` + filter）
  ⇒ 英雄仍可能去**拦** boss，只是拦到之后只会用没被 ban 的那条招式（本例是普通近战）打。
- 数据事实（离线枚举 380 个 `enemy_*` 模板）：**33 个带 `F_BOSS`**（含 `enemy_miniboss_stage_39`、`enemy_boss_stage_*`、
  `enemy_twilight_brute` 等），且**没有"`lives_cost` 高但没打标签"的漏网 boss**（lives_cost ≥15 而不带 F_BOSS 的 = 0）
  ⇒ 用 flag 判定足够，不必再按 `enemy.lives_cost` 兜。
- ⭐ **双保险写法**（推荐）：除了攻击的 `vis_bans`，在**真正生效的那个函数**开头再判一次
  `if band(target.vis.flags, bor(F_BOSS, F_MINIBOSS)) ~= 0 then 清理并 return end`
  —— 因为"能挂上 mod 的路径"可能不止一条（其它机制/将来改配置）。
- ⚠ `F_BOSS` 位不与 `F_ENEMY`/`F_FRIEND` 重叠 ⇒ 这个判定**不会误伤普通敌人**（探针里有正的/负的两向断言）。
- 探针写法：**别只断言"模板上有 ban"**，要断言"**引擎会在选招时用这个字段**"（结构断言）
  + 真跑一次生效函数（拿一个真带 F_BOSS 的模板当目标、store 里**故意不给 hero**，
  兜底生效则函数不会走到读 `hero.…` 那行 ⇒ 用"没崩在 hero 上"当通过判据）。

#### ⭐⭐ "这个位置站得住吗"：用 `U.has_valid_rally_node_nearby(pos)`（2026-10-08 实证）

禁止"策反/附身/召唤到**水里**（或任何站不住的地方）"时，**别自己写地形判断** —— 引擎原生策反
`SU.is_valid_betray_target`（`all/script_utils.lua:5276`）已经有官方口径：

```lua
U.has_valid_rally_node_nearby(pos)
-- = GR:cell_is_only(pos.x, pos.y, bor(TERRAIN_LAND, TERRAIN_ICE))
--   and P:valid_node_nearby(pos.x, pos.y, nil, NF_RALLY)
```

① 所在格**只能有 LAND/ICE 位**（水 / 悬崖 / NOWALK 一律不通过）；② 附近**有合法 rally 节点**。
第②条对"生成一个要自己走位的单位（士兵类）"尤其重要：它保证那个点是**它自己站得住、能回位**的地方。

⚠⚠ **离线（探针 / 没有关卡）时 `GR`/`P` 没加载，这个函数会直接报错**
（实测 `lib/klua/macros.lua:53: attempt to compare number with nil`，因为 `cell_is_only` 里
`band(nil, …)` 走进了数值比较）⇒ 包一层 `pcall` 并 **fail-open**（读不到地形就照旧放行），
否则探针里的假目标单测会全线崩（我第一版就差点这么干）。

验证写法（离线也能证明语义）：直接套引擎公式算一遍常量 ——
`band(TERRAIN_WATER, bnot(bor(TERRAIN_LAND, TERRAIN_ICE))) ~= 0` ⇒ 水格必不通过；
LAND/ICE 各自 `== 0` ⇒ 通过 ✓。比"真跑一遍地形"更可靠（离线没有关卡数据）。

#### ⭐⭐ 同一位（bit）的别名、以及"变形单位"这类特殊标记（2026-10-08 `hero_zezitra` 实证）

`all/constants.lua` 里**多个名字共用一位**（历史遗留），判定时极易误伤：

| 位 | 共用这个名字的常量 |
|---|---|
| `16777216` | **`F_RAGGIFY` / `F_THORN` / `F_TWISTER` / `F_FLYING_FAKE`** |
| `1073741824` | `F_LYCAN` / `F_DARK_ELF` |
| `536870912` | `F_SERVANT` / `F_UNDEAD` |
| `32` | `F_BOSS` / `F_MINIBOSS` |

⇒ 同一个位在 **`vis.flags`** 上和在 **`vis.bans`** 上语义完全不同：
例：位 `16777216` 在 `vis.flags` 上是"幽灵类的 flying-fake"（`enemy_ghost` / `enemy_phantom_warrior`），
在 `vis.bans` 上才是我们用的"**已策反**"标记。**判 `bans` 还是判 `flags` 必须按语义选，不能混。**

**"变形单位"要排除（`F_POLYMORPH = 2097152`）**：离线扫全部敌人（`.workbuddy/scan_enemy_flags.lua`）得到
- **`vis.flags` 带 `F_POLYMORPH` 的只有 2 个模板**：`enemy_pumpkin_witch` / `enemy_pumpkin_witch_flying`
  （`kr1/heroes.lua:12221/12240`，两形态同源；由英雄女巫的 `mod_hero_skill_polymorph` 把敌人变成的南瓜）
  ⇒ 这是"**变形术产物**"标记，策反它没意义（原形态随时恢复）。
- ⚠ **`vis.bans` 带 `F_POLYMORPH` 的有 56 个**（骷髅 / boss…）= "**免疫**变形"，语义完全不同
  ⇒ **拿 bans 去判会把一大片正常敌人误排掉**（`mod_polymorph.insert` `all/scripts.lua:7388` 读的就是 bans）。

⇒ 排除变形单位同样做**三层**：攻击条目 `vis_bans`（引擎层）+ 目标挑选函数 + 挂 mod 的生效层。
⚠ 给"纯谓词"函数加新条件时，**先看既有单测喂进来的假对象有没有那个字段**
（本次直接写了 `target.vis.flags`，而单测喂的假目标没有 `vis` ⇒ `attempt to index field 'vis' (a nil value)`，
被探针当场抓到）⇒ 写成 `target.vis and band(...) ~= 0`。



### ⭐ 想让技能"自动触发"时：引擎通道的能力边界（2026-10-04 `hero_zezitra` 实证）

- ⚠ **`timed_attacks` 通道本身不带筛选回调**：`SU.y_soldier_timed_attacks`
  （`all/script_utils.lua:1934`）用 `U.detect_foremost_enemy_between_range_filter_off` 选目标
  ⇒ 只有 `vis_flags` / `vis_bans` 两个位过滤，**`fn_can` / `filter_fn` 在这条路径上不会被调用**。
  ⇒ 想加"血量门槛 / 更复杂条件"的技能**别以为挂上 `timed_attacks` 就完事**：
  要么在自己主循环里写触发（用 `detect_foremost_enemy_between_range_filter_on(..., filter_fn)`），
  要么走 `ranged` / `melee` 路径（那两条会读 `attack.filter_fn`，见 `:1627`）。
- ⚠⚠ **`detect_*_enemy_*` 的 flags/bans 参数是「反向映射」**：`all/seek.lua:45`
  `enemy_filter_simple(e, P4, P5) = band(e.vis.bans, P4) == 0 and band(e.vis.flags, P5) == 0`
  ⇒ **"目标不能带哪些 flag"（飞行/BOSS…）要传给第 5 个参数 P5**（P4 查的是目标的 `vis.bans`）。
  **传错位置 ⇒ 过滤静默失效**（技能照样放，只是不该打的目标也被打了）。
  （对比：写模板攻击的 `vis_flags`/`vis_bans` 字段时，语义是引擎那套"目标需有/不能有"，
  与这里传参的位置不同 —— 别把两者混为一谈。）
- 现成范式（自动触发 + 短重试）可照抄 `hero_zezitra` 主循环里"暗影双生 / 蛇语蛊惑"那两段：
  ```lua
  a = <timed_attacks 条目>
  if a and not a.disabled and store.tick_ts - a.ts > a.cooldown then
      local target = U.detect_foremost_enemy_between_range_filter_on(this.pos, a.min_range, a.max_range,
          0, a.vis_bans, function(e) return <门槛回调>(...) and not U.has_modifiers(store, e, a.mod) end)
      if not target then
          SU.delay_attack(store, a, 0.1333)   -- 无目标：短延迟重试（别每帧空转）
      else
          S:queue(a.sound); U.animation_start(this, a.animation, nil, store.tick_ts)
          if SU.y_hero_wait(store, this, a.shoot_time) then --[[ 被打断 ]]
          else
              a.ts = store.tick_ts
              SU.hero_gain_xp_from_skill(this, this.hero.skills.<x>)
              local mod = E:create_entity(a.mod); mod.modifier.target_id = target.id; ...; queue_insert(store, mod)
              SU.y_hero_animation_wait(this); goto <帧尾 label>
          end
      end
  end
  ```
  ⭐ `SU.delay_attack(store, atk, t)` 的语义 = `atk.ts = now - cooldown + t`（**t 秒后即可重试**），
  不是"把 CD 拉满"。



### ⭐⭐ 把敌人"暂时移出场面"就必须懂 `count_groups` 的 limbo 账（策反 / 吞噬 / 放逐类机制）

`all/systems/count_groups.lua`（只有 40 行，值得全文读）：
- `on_remove_unconditional`：`if entity.count_group and not count_group.in_limbo and type == COUNT_GROUP_CONCURRENT then 递减 end`
- `on_insert_unconditional`：`if count_group.in_limbo then in_limbo = nil; return true end`（**清标记并跳过一次递增**）

⇒ 正确用法（"临时离场、稍后回来"）：
1. 离场：`target.count_group.in_limbo = true` → 再 `queue_remove(target)` ⇒ 引擎**不减**（计数保留，场面上少一个但名额还占着，刷怪器不会趁机灌怪）。
2. 回来：**保留 `in_limbo = true` 直接 `queue_insert(target)`** ⇒ 插入钩子自己清标记并**跳过递增** ⇒ 净账为零。
3. **回不来**（被打死 / 被消耗）：必须**补一次递减** —— 把 `in_limbo` 清 nil 后手动调
   `require("all.systems.count_groups"):on_remove_unconditional(target, store)`。
   ⚠ 漏了 ⇒ `store.count_groups` 只增不减 ⇒ 刷怪器的 `cg[name] >= count_group_max`
   （`all/scripts.lua:1224`）越卡越死 ⇒ **后面几波可能永远刷不出来**（关卡卡死）。
- ⚠⚠ **别在 insert 前手动清 null**：`KR1` 原版就是先 `target.count_group.in_limbo = nil` 再 insert ⇒
  钩子的早退分支失效 ⇒ **每次循环 +1 漂移**（2026-10-04 `hero_zezitra` 实证并修掉）。
- 排查手法：`grep -rn "in_limbo" all/ kr1/` —— 引擎里凡是"把单位移出场面又打算拿回来"的技能
  （boss 束缚、raggify 变羊、策反）都会成对出现 `= true` / `= nil`；错在哪一侧一读就知道。



### ⭐⭐ 「`clone_entity` → `create_entity`」= 换契约：逐组件过一遍

原版"策反/召唤"类代码常用 `E:clone_entity(敌人)`（`all/entity_db.lua:397` 整表深拷贝）
⇒ 拿到的实体**每个组件都已是运行值**。换成 `E:create_entity(自己的模板)` 后，
"原版默认就有的东西"全都要**自己补**。照着 clone 会带的东西列清单（每一项都是踩过的坑）：

- `health.hp`（默认 **nil**，见上文）· `health.hp_max` · `health.armor`/`raw_armor` ·
  `magic_armor`/`raw_magic_armor`（护甲是"重甲敌人变友军"最容易漏的一项）
- `render.sprites[*]`（**逐层**）、`unit.size/hit_offset/mod_offset/marker_offset`、`health_bar.offset`
- `melee.attacks` / `timed_attacks`（**深拷贝**，别共享引用）
- `motion.max_speed`、`nav_rally.pos/center`、`vis.flags/bans`
- ⭐ 判据：**"原版那行代码能跑，只是因为它身边的对象是 clone 来的"** ⇒ 换构造方式就要重新付这份账。

### ⭐⭐ 移除"会 block 的友军"时必须先解阻挡（否则敌人永久卡住）

宠物/召唤物/移动塔这类友军带 `melee.attacks[*].vis_flags = F_BLOCK` ⇒ 它会 `block_enemy`
（把 id 写进敌人的 `enemy.blockers`）。**任何不走 `SU.y_soldier_death` 的移除路径**
（`replaced` 顶替、超时回收、直接 `queue_remove`）都要先 `U.unblock_target(store, this)`：
否则敌人的 `enemy.blockers` 里留下一个**已不存在的 id**，而引擎判定"被阻挡"只看这个列表
⇒ **该敌人永久停在原地不走**。`SU.y_soldier_death`（`all/script_utils.lua:1371`）本身就是先 unblock；
Chen 另有 `release_servant_block` + `prune_servant_block_refs` 双保险（连"别的敌人身上记着我"也清）。
⚠ KR1 原版自己就漏了这条（顶替分支只置 hp=0 后 `queue_remove`），照搬会继承这个 bug。

- 涉及「克隆敌人当友军」时：**别用 `E:clone_entity`**，改用 `E:create_entity("<soldier 系模板>")`
  + 拷外观/行为（Chen 插件 `create_servant_from_enemy` 范式；本项见 `hero_zezitra` 的
  `create_entity("soldier_possessed_pet")`）。
  ⚠ **行为表（`timed_attacks.list` / `melee.attacks`）必须深拷贝**（`table.deepclone`，`lib/klua/table.lua:124`
  已全局安装）：原敌人只是进 limbo 且稍后会复活，共享引用会被宠物 update 污染。
  ⚠ 且**必须拷**：`soldier_possessed_pet` 模板 `timed_attacks.list` 为空，而宠物 update 读 `list[1]`/`list[2]`
  （`tac.count_group_type`）⇒ 不拷直接索引 nil 崩。
  ⚠⚠ **手动拷 sprite/组件字段必须逐字段防 nil**（2026-10-04 `hero_zezitra` 蛊惑宠物真机崩
  `systems.error on_update() - Error running mod_possession_pet coro: lib/klua/vector.lua:113: attempt to index local 'vec' (a nil value)`）：
  `sprite` 组件**大量字段默认就是 nil**（`scale` / `angles` / `draw_order` / `size_names`…，
  `all/components.lua` `E:register_c("sprite")`），其中 **敌人模板基本不写 `scale`**
  （离线抽查 423 个敌人模板只有 18 个写）⇒ 裸 `V.vclone(src.scale)` 必崩（`vclone` 里 `vec.x` 索引 nil）。
  **写法**：`dst.x = src.x and V.vclone(src.x) or nil` —— **nil 语义原样保留**，别补成 `v(1,1)` 之类的猜测值。
  ⚠ 敌人**可能有多层 `render.sprites`**（74/423 个 >1，如 `enemy_zealot` 3 层、`enemy_perython_rock_thrower` 3 层）
  ⇒ 拷外观要**逐层**拷，缺层用 `E:clone_c("sprite")` 补。（`exo` 字段是 **boolean 标志**，不是对象。）
  ⭐ 抽成**可离线单测的 helper**（`copy_sprite_visual` / `copy_visuals`），判据 = **探针真的把 nil 传进去跑过**，
  静态 grep 只防回退。
- 涉及 `find_soldiers_in_range` 时：在 `filter_func` 里补 `e.soldier`（英雄也带 `.soldier`，
  `all/templates.lua:953` `hero = E:register_t("hero","soldier")` ⇒ 不会被误滤）。
- 涉及**信息条显示**时（`tt.info.fn = ...`），两条路要按数据形态选：
  - **改走 `scripts.hero_basic.get_info`**（= `soldier_barrack.get_info`，`all/scripts.lua:520-645`）——
    引擎标准口径，字段名天然对；但**近战只认"第一个有 `damage_min` 的 attack"**，
    且**远程只认 `b.bullet.damage_min/max`**（`:554`）。
  - **保留自带 `get_info`**，把返回字段名改成 Dove 口径 + 补 `cooldown` / `ranged_cooldown`
    （CD 乘 `unit.cooldown_factor`，口径见 `all/scripts.lua:539-541` / :570-572）。
  - ⭐ **判据**：若伤害走 **`damage_*_levels` 数组**（`bullet.damage_min` 刻意写 nil）⇒ **必须保留自带**，
    否则标准版判为"无远程"。反之若就是普通 `bullet.damage_min/max` ⇒ 直接用标准版最省事
    （ember / viper 就是这么做的，但它们的远程是普通弹丸）。

### ⭐⭐ 移植前先确认「那段原版代码在原版里真的会执行」（2026-10-04 `hero_zezitra` 实证）

反编译出来的脚本**可能是死代码**：函数在、模板也引用了，但**没有任何地方会创建那个模板**。
`hero_zezitra` 就踩了这个坑 —— 移植的 `scripts.soldier_possessed_pet.update`（宠物 AI）在原版里
**没有任何模板会被 create**；原版真正的宠物是 `E:clone_entity(敌人)` 跑的
**`enemy_basic` 的 `soldier.pet` 士兵 AI 分支**（`all/scripts.lua:724` 起）。
照搬死代码 = 连同它**隐含的模板契约**一起搬，而那个契约（"宠物必有 2 条 `timed_attacks`"）在真实数据上不成立：

| 数据事实（离线实测 2026-10-04） | 数量 |
|---|---|
| Dove `enemy_*` 模板总数 | 380 |
| `timed_attacks.list` **0 条** | 298 |
| **1 条** | 73 |
| **≥2 条** | **9** |

⇒ `tac = this.timed_attacks.list[2]` 后面紧跟 `store.count_groups[tac.count_group_type]`，
**几乎必崩**（真机 `attempt to index local 'tac' (a nil value)`）。
**修法**：`local tac = this.timed_attacks and this.timed_attacks.list[2]` + `if tac then … end` 全段 guard
（那两三个字段只服务于敌人专属分支，取不到就整块跳过，不影响普攻/自爆/光环）。

**动手前的三问**（省一轮真机迭代）：
1. 这段代码**谁调用**？`grep` 模板名 + 脚本名，确认有 `create_entity` / `main_script.*=` 指向它；
   找不到 ⇒ 很可能是死代码，**优先照抄原版真正的行为路径**。
2. 它读的每个字段，**在原版是谁保证存在的**？（clone 带来的？模板默认值？插入时补的？）
3. 这些保证换到 Dove 的实现里还成立吗？（换构造范式 / Dove 回归改动 / 数据分布都会破坏它）


- ⭐ **`sound_db.sound_extras[id]` 条目形态随引擎版本变过三次，mod 补丁必须 type 分流**（2026-10-06 balloon_crash "attempt to index local 'se' (a number value)" 实证）：
  旧版=散列表 `{last_play_ts, every_counter}`（缺了补表即可）；中间版=FFI 数组**数字下标**；新版（`all/sound_db.lua:174 _precache_sound`）=`_extras_arr + _extras_cnt` 的 **cdata 指针**。
  给 `S.sounds[id]` 直接赋值注册的自定义音效（绕过 `register_sounds`）在新版引擎里没有 extras 条目 ⇒ 引擎 `play()` 里 `se.last_play_ts` 直接崩。
  **正确做法**：注册自定义音效后调 `S:_precache_sound(id, sd)`（存在才调，老引擎退回 `S.sound_extras[id] = S.sound_extras[id] or {}`）；包装 `S:play` 做兜底时，对条目**按 type 分流**——table 才补字段，number/cdata 一律不碰（对数字/cdata 取字段就是崩溃根因）。同类补丁散布在 alien_bug_nest / DemonRealm / ember_hero / hero_viper / hero_zezitra / johnny_deadeye / toxic_tomato / TrollAxeThrower / weird_archer 等插件里（全是 `or {}` 旧写法），游戏更新到中间版/新版时都会以同样方式崩。

### ⭐⭐ 改完必须同步 AppData —— 游戏只读那里，工程目录里的 `mods/` 不生效（2026-10-20 定型）

- **真实加载路径**：`C:\Users\<user>\AppData\Roaming\LOVE\kingdom_rush_dove\plugins\<entry>\`
  （工程里的 `KingdomRushDove\mods\local\<entry>\`、`mods\我的插件\<entry>\` 只是源码副本）。
  查有没有推过：直接 `diff -q` 两边同名文件，别靠时间戳猜。
- **逐类文件的推法**：
  | 文件 | 做法 |
  |---|---|
  | `*.lua`、`readme.md` | 直接覆盖 |
  | `config.lua` | ⚠ **禁止整份覆盖**。游戏在安装/更新/应用插件时会回写 `last_used_at`（`plugin_manager_view.lua:1906` 等），整份覆盖会丢掉游戏侧状态并让版本号打架。只替换版本行：`re.sub(r'version = "[^"]+"', 'version = "x.y.z"', s)`。**2026-10-21 又踩了一次**：`cp` 整份推四个插件，`last_used_at` 从游戏侧的 `1792555506` 被退回源码里的旧值，得手工 spot 还原。判据：`diff 备份 vs AppData` 若 `last_used_at` 也出现在差异里，就是覆写过头了 |
  | `*.lua.bak` | 不要推；AppData 里已经存在的顺手删掉（那是本地备份，不该出现在游戏插件目录） |
  | `<entry>.zip` | 重打包后覆盖（见下面第 5 条） |
- ⚠⚠ **游戏运行中推送不生效**：`love.exe` 已把 lua 模块读进内存，覆盖磁盘后行为不变，必须重启游戏。判断在跑：`tasklist | grep -i love`。
- ⚠⚠ **游戏运行中别在插件管理器点「应用」**：`_set_enabled` / `on_toggle`（`plugin_manager_view.lua:2572`、`:4500`）
  只改**内存里的 cfg 表**，点应用时整表写盘 —— 内存里是启动时读的旧 `version`，于是刚改的版本号被退回旧值。
  **先重启游戏，再动插件管理器。**（2026-10-20 实测：21:24 的 `last_used_at = 1792502667` 就是这么来的，同时把 0.3.12 写回成 0.3.11。）
- **校验同步结果**：`lua_syntax_check.py` 一次传工程副本 + AppData 副本，两边都 OK 才算同步成功。
  ⚠ Python 不认 Git Bash 的 `/c/...`，路径必须写 `C:/Users/...`（否则 `FileNotFoundError`，别误判成文件丢了）。

2. 验证：**首选语法校验**——用游戏自带的 `lua51.dll`（工作区根目录）直接真编译，零依赖、零启动开销：`python .workbuddy/lua_syntax_check.py <lua文件...>`（ctypes 调 `luaL_newstate`/`luaL_loadstring`，非 0 时用 `lua_tolstring` 取带行号的错误；必须先 `os.add_dll_directory(ROOT)`，因为 lua51.dll 依赖同目录的 msvcr120.dll；记得剥 UTF-8 BOM）。批量校验时把工作区副本和 AppData 副本一起传入，顺带确认同步。备选 `luaparser`（pip install luaparser，纯 Python）。再 `./lovec.exe KingdomRushDove > 日志 2>&1`，必须**后台方式启动**（前台 `&` 会随命令结束被杀，日志截断在 204 行），lovec stdout 是块缓冲，完整日志要等进程退出后 grep；有时 lovec 日志为 0 字节，此时以语法校验 + 游戏内实测为准。
2-bis. **零依赖备选：`lovec.exe` + 临时 Love 项目做 `loadfile` 语法校验**（2026-10-02 实战，不需要 Python/ctypes）：
   - 在纯 ASCII 目录（如 `C:/tmp/luacheck/`）建 `conf.lua`（`t.window=false`、关掉 graphics/audio 模块）+ `main.lua`：
     ```lua
     local files = { "scripts.lua", "xxx.lua" }   -- 待检文件名
     local base  = "C:/tmp/luacheck/src/"          -- 待检文件所在的 ASCII 目录
     local out, ok_all = {}, true
     for _, f in ipairs(files) do
         local fh, err = loadfile(base .. f)
         if fh then table.insert(out, "OK   "..f)
         else ok_all = false; table.insert(out, "FAIL "..f.." => "..tostring(err)) end
     end
     table.insert(out, ok_all and "ALL PASS" or "HAS ERRORS")
     local w = io.open("C:/tmp/luacheck/result.txt","w"); w:write(table.concat(out,"\n")); w:close()
     love.event.quit()
     ```
   - 跑：`cd 王国保卫战Dove版 && ./lovec.exe C:/tmp/luacheck`，然后读 `result.txt`（stdout 被块缓冲吞，写文件最稳）。
   - ⚠⚠ **必须先把 .lua 复制到纯 ASCII 路径**：`loadfile` 对含中文的路径（工程目录名「王国保卫战Dove版」）报
     `cannot open ...: Invalid argument`（Lua 5.1 的 ANSI `fopen`）——**这是路径问题，不是语法错误**，别误判。
   - 同理 `/tmp` 在 Git Bash 与原生 exe 下**不是同一目录**（原生 exe 看到的 `C:/tmp/`），临时目录统一写 `C:/tmp/...`。
3. 图集：FL 图组提取用 `.workbuddy/extract_leaf_sprites.py` 模式（去行内注释、容忍坏帧、生成后校验 lua）；原版图组加载必须 `I:load_atlas_new`，本地图集用 `I:load_atlas(1, path, name)`。
4. 模板注册 HOOK `entity_db:load`（E.load），注册发生在 entities_backup 前，可跨开局存活。
5. **打包发布 zip**：Git Bash **没有 `zip` 命令**（`zip: command not found`）。**首选 Python `zipfile`**（能排除垃圾文件、能自检）：
   ```python
   files = sorted(f for f in os.listdir(d) if f.endswith((".lua", ".md", ".txt")))  # 排除 .bak / *.zip
   with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
       for f in files: z.write(os.path.join(d, f), f)   # 平铺，不建子目录
   zipfile.ZipFile(zp).testzip()                        # 返回 None 才算好
   ```
   ⚠ **插件 zip 是平铺结构**（不带 `<entry>/` 顶层目录），重打前先 `zipfile.ZipFile(old).namelist()` 看一眼旧包层级，别自作主张加子目录。
   ⚠ **打完必须核对包内每个文件的字节数**：常见事故是"刚改了 pager，包里的还是旧版"（2026-10-20 实见：zip 里 pager 4680 字节，磁盘已 4905）。按"打包时间 vs 各文件 mtime"比一遍。
   备选 PowerShell `Compress-Archive -Path <文件们> -DestinationPath <zip> -Force`；
   `Add-Type` 会被安全策略拦（"compiles and loads .NET code at runtime"），列 zip 条目改用 `unzip -l`。
