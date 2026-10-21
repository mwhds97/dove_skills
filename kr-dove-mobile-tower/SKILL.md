---
name: kr-dove-mobile-tower
description: 王国保卫战 Dove 版把防御塔改造成"可被玩家点调集的移动塔"的完整做法：独立模板 + motion/nav_rally/nav_grid 三件套、塔菜单注入自定义按钮进入 GUI_MODE_RALLY_CONTROABLE、边走边开火的脚本改造（刷新 tpos + 位移版等待）、禁售防止白送塔位、底座占位符处理、开局赠礼时机与"独立插件 vs 地图内实现"的作用域取舍（模板注册时机决定只在哪张图生效）。做可移动/可调集/会走路的塔，或塔菜单加自定义按钮、把塔功能整合进某张地图、排查"点了选不中/走不动/移动后仍打原地/所有地图都冒出来"时使用。
agent_created: true
---

# KR Dove 版：可调集移动塔

适用：把某座防御塔做成"像英雄/士兵那样被玩家点选派往任意位置，边走边打"的独立塔；或给塔菜单加自定义按钮；或把已经写好的独立插件版**整合进某张地图**（见 §九）。

参考实现：
- 地图内版本（推荐，作用域干净）：`mods/local/Tropical_Loop/mobile_magus*.lua` + `data/levels/Tropical_Loop.lua`
- 独立插件版·赠送特殊塔（已 `enabled = false` 保留作对照）：`plugins/mobile_wild_magus`
- 独立插件版·改造原版塔（玩家建造的塔可移动 + 恢复塔位）：`plugins/movable_wild_magus`（路线 B，见 §二）

## 一、为什么不能直接"点选进调集"

`game_gui:select_entity`（all-desktop/game_gui.lua:1388）分支顺序：

```lua
if e.tower then game_gui.towermenu:show()
elseif e.hero then self:set_mode(GUI_MODE_RALLY_HERO)
elseif e.controable then self:set_mode(GUI_MODE_RALLY_CONTROABLE) end
```

**塔永远走 `e.tower` 分支 → 点选进不了调集模式。**
唯一入口是在自建塔菜单页加一个按钮，回调里主动切模式：

```lua
local gg = require("game_gui")
gg:set_mode(GUI_MODE_RALLY_CONTROABLE)   -- 清掉 nav_grid.waypoints 让落点重新寻路
```

调集点击处理在 game_gui.lua:7395 的 `GUI_MODE_RALLY_HERO or GUI_MODE_RALLY_CONTROABLE` 分支，三个条件全过才成功：

1. `not e.nav_rally.requires_node_nearby or P:valid_node_nearby(wx, wy, nil, NF_RALLY)`
2. `GR:cell_is_only(wx, wy, e.nav_grid.valid_terrains_dest)`
3. `e.teleport... or e.nav_grid.ignore_waypoints or GR:find_waypoints(e.pos, e.nav_rally.pos, V.v(wx,wy), e.nav_grid.valid_terrains)`

成功后写：`e.nav_grid.waypoints`、`e.nav_rally.new = true`、`e.nav_rally.pos/center = v(wx, wy)`。

> 想"全图自由走"：`tt.nav_rally.requires_node_nearby = false`（跳过条件 1）；
> 想"只能落脚陆地/冰面"：`nav_grid.valid_terrains = nav_grid.valid_terrains_dest = bor(TERRAIN_LAND, TERRAIN_ICE)`。

### ⭐⭐ 反向情形：**友方士兵 / 召唤物**要"可点选调集" —— 一个标记搞定，别学塔那套（2026-10-04 `hero_zezitra` 宠物实证）

塔之所以要自建菜单按钮，是因为 `select_entity` 第一个分支就把塔吃掉了。**士兵/召唤物没这个问题**：

```lua
if e.tower then game_gui.towermenu:show()
elseif e.hero then self:set_mode(GUI_MODE_RALLY_HERO)
elseif e.controable then self:set_mode(GUI_MODE_RALLY_CONTROABLE) end   -- ← 只差这个标记
```

⇒ 给友方士兵模板加 **`tt.controable = true`** 即可"点它 → 点地面 → 走过去"，**不需要任何点击钩子**。
现成参考：原版 `soldier_gerald_paladin`（Gerald 召唤的圣骑士）、
`mods/local/werewolf_house` 的"感染狼人" `soldier_werewolf_wolf`（该插件 `_templates.lua:157-203`）。

- **`controable_other = true` 的语义**（`all-desktop/game_gui.lua:897` vs `:1015`）：两个
  "集结全部可控单位"热键分别收 `not controable_other` 与 `controable_other` 两组。
  **原版所有英雄都是 `true, true`** ⇒ 想让该单位**不被"集结全部士兵"热键一起拖走**就写 `true`
  （宠物/召唤物推荐，与英雄同组）。
- 还需要 **`nav_grid`**（点选要写 `nav_grid.waypoints`；组件默认 `valid_terrains = LAND|ICE`）
  与 **`nav_rally`**，且**该单位自己的 update 会消费 `nav_rally.new`**（否则点了不动）。
  ⚠ 复用原版兵营/召唤脚本（`scripts.soldier_barrack` / `soldier_reinforcement`）时天然满足；
  自定义单位要确认循环里有 `while this.nav_rally.new do ... end` + 清 `new` 的那处消费者。
- ⚠ `nav_rally` ffi 默认 **`requires_node_nearby = true`**（`all/components.lua:95` 第 4 参）⇒
  落点必须靠近导航节点（与兵营口径一致；werewolf_house 也没改）。要"草地上也能派"就置 `false`。
- ⚠ "点了不走"的另一种原因：单位脚本每帧用别的坐标覆盖 `motion.dest`（自动索敌/回巢）
  ⇒ 要么禁掉那段，要么加"手动优先"标记（见下）。

**⭐ 让"手动派出去"不被别的逻辑拉回**（例：既有"英雄改集结点就把宠物拉回来"的派发逻辑）：
用**来源标记**区分"谁下的令"，比 HOOK 点击稳：

```lua
-- 下发方（英雄派发）多写一个标记：
p.nav_rally.center, p.nav_rally.pos = pos, pos
p._hero_rally = true          -- "这单是英雄下的"
p.nav_rally.new = true
-- 消费方（单位脚本里清 nav_rally.new 的那唯一一处）判定来源：
if this._hero_rally then this._hero_rally = nil else this.manual_rally = true end
-- 派发方循环里跳过：if p and not p.manual_rally then ... end
```

## 二、独立模板（不影响原版塔）

**两条路线，先选再动手**：

- **路线 A：派生独立模板**（本节写法）—— 原版塔零改动。代价：新 `tower.type` 查不到原版科技
  （mage_brilliance 按 `template_name` 查表）、菜单页要自建、购买/赠送逻辑全要自己做。
- **路线 B：直接改原版模板**（`movable_wild_magus` 插件，"玩家建造的塔可移动"用这条）——
  在 E.load 钩子里对原模板（如 `tower_wild_magus`）本体 `AC` 三件套 + 换 main_script，
  **tower.type 不变**：菜单页（直接往 `tmd.wild_magus[1]` 追加 `M(tpl.rally, {action="自定义", place=空位})`）、
  科技、升级链（3 级法师塔升级而来）全部照旧，玩家建造出来的塔自动获得能力。
  ⚠ 玩家建造的塔**占着塔位**：首次移动时（`nav_rally.new`，塔还在原位）要照
  `all/systems/tower.lua:174-195` 出售分支在原地重建塔位 ——
  `E:create_entity(tower.terrain_style)` + 继承 pos/holder_id/flip_x/default_rally_pos/nav_mesh_id →
  `queue_insert_entity`（不删塔不退钱），然后自身 `sprites[1].hidden = true` +
  `tower.can_be_sold = false`（**必须禁售**：出售流程会按 terrain_style 再建一个塔位，移动后卖=白嫖建造位；
  实体级禁售即可，game_gui.lua:8254 会直接不创建 tw_sell 按钮）。
  ⚠ `holder_id` 运行时无逻辑依赖（只编辑器数据链/endless 恢复/塔位脚本补 id 在用），保留不动即可。
  ⚠ 单级塔（无 upgrade_to 链、powers 升级不重建实体）没有断链问题；有升级链的塔要另处理
  升级"换实体"后 hidden/禁售状态的丢失。

```lua
require("all.constants")
local bit = require("bit")
local cfg = require("<entry>.<entry>_config")
local scripts = require("<entry>.<entry>_scripts")

local tt = RT("tower_mobile_<x>", "tower_<base>")   -- 从原版塔派生
AC(tt, "motion", "nav_rally", "nav_grid")           -- 三件套

tt.tower.type = "mobile_<x>"        -- 独立塔类型 → 独立塔菜单（关键）
tt.tower.price = 0
tt.tower.can_be_sold = false        -- 见 §四

tt.motion.max_speed = cfg.speed_per_frame * FPS     -- 单位是"像素/帧"（FPS=30）
tt.motion.factor, tt.motion.buff = 1, 0

⚠⚠ **绝不把 `motion.max_speed` 当"当前速度"直接写**：`motion.real_speed` 只在
`hook:on_insert_unconditional` 里由 `max_speed` **同步一次**（且在 `main_script.insert` **之后**跑）。
所以：

- **想改速度** → 改 `max_speed`，或在 `insert` 里自己补 `this.motion.real_speed = this.motion.max_speed`
  （插入前同步见 §四）；运行时调速用封装 `U.speed_mul_self` / `U.update_max_speed`，
  别裸改 `real_speed`（下一帧会被 max_speed 覆盖回去，表现为"改了没反应"）。
- 离线桩里若实体没走完整 insert 流程，`real_speed` 可能是 nil → 主循环 `pos += real_speed` 直接崩。

tt.nav_rally.requires_node_nearby = false
tt.nav_grid.valid_terrains = bor(TERRAIN_LAND, TERRAIN_ICE)
tt.nav_grid.valid_terrains_dest = bor(TERRAIN_LAND, TERRAIN_ICE)
tt.nav_grid.ignore_waypoints = nil

tt.controable = true                -- 与英雄/士兵语义一致（会被框选类插件认可）
tt.controable_other = nil
tt.info.i18n_key = "MOBILE_<X>"
tt.info.fn = scripts.get_info
tt.main_script.insert / update / remove = scripts.insert / update / remove
```

要点：

- `nav_rally` 是 **ffi cdata**（lib/nav_rally.lua，`vec2 pos; vec2 center; bool requires_node_nearby; bool new`）。
  `pos:copy(vec2)` 原地改；`e.nav_rally.pos = v(x,y)` 按值写。`table.deepclone`（lib/klua/table.lua:82）对带 `clone` 的 cdata 调 `:clone()`，所以 `AC(tt, "nav_rally")` 深拷安全。
- `tower.level` 必须有值（基础模板 `all/templates.lua:873 tower.tower.level = 1` 已给），否则 `TowerMenu:show` 查 `tmd[type][level]` 落空直接 `hidden`。
- **模板注册位置决定作用域**（详见 §九）：
  - 写成**独立插件**就放 `HOOK(E, "load")`：注册发生在 `entities_backup` 建立**之前**，可跨开局存活
    —— 代价是**每张地图都会有这座塔**。用 pcall 包住，避免阻断后续插件的 E.load 链。
  - 写成**地图内实现**就放 `level:init`（`E:Load()` 之后）：不进 `entities_backup`，
    每次开局还原时被清掉 → **只在那张图存在**。两种时机不要混用。
- `DI:patch_templates()` 只缩放 `t.soldier` / `t.enemy`，tower 根模板不受难度影响。

## 三、边走边开火：脚本改造两处

原版塔脚本（如 `kr1/tower_scripts.lua:1791 scripts.tower_wild_magus.update`）有两个致命点：

1. **`local tpos = tpos(this)` 写在协程开头**，之后全程复用这个快照 → 塔移动后索敌/开火原点停在原地。
   → 改 `refresh_tpos(this, tp)`，在 `while true` 每轮开头、以及每次等待之后重算 `tp.x, tp.y = this.pos + this.tower.range_offset`。
2. **`U.y_wait_unconditional` / `U.y_animation_wait` 是纯阻塞等待**，期间不动。
   → 换成"每帧继续推进位移"的本地等待：

```lua
local function y_move_wait(store, this, time)
	local stop_ts = store.tick_ts + time
	while store.tick_ts < stop_ts do move_step(store, this); coroutine.yield() end
end

-- times 语义必须与原版 U.y_animation_wait 一致：a.loop and (times or 1) or 0
local function y_move_anim_wait(store, this, sid, times)
	local a = this.render.sprites[sid]
	times = a.loop and (times or 1) or 0
	while a.runs <= times do move_step(store, this); coroutine.yield() end
end
```

`move_step(store, this)` 的核心（**必须做同 tick 去重**，因为等待里已经走过一次）：

```lua
if r.new then                       -- GUI 写的"新集结指令"
	r.new = false; n.waypoints = n.waypoints or {}
	this.__mw_moving, this.__mw_need_dest = true, true
end
if not this.__mw_moving then return false end

if this.__mw_need_dest then
	local w = table.remove(n.waypoints, 1) or r.pos   -- 兜底用 nav_rally.pos
	this.__mw_need_dest = false
	if not w then this.__mw_moving = false; return false end
	if dist2(this.pos.x, this.pos.y, w.x, w.y) < 1 then m.arrived = true
	else
		U.set_destination(this, w)                      -- 置 motion.dest + arrived=false
		local an, af = U.animation_name_with_direction(this.render.sprites[sid_shooter], "idle", dx, dy)
		U.animation_start(this, an, af, store.tick_ts, true, sid_shooter)   -- 第5参是 loop
	end
end

if m.arrived then
	if #n.waypoints > 0 or dist2(this.pos.x, this.pos.y, r.pos.x, r.pos.y) > 1 then this.__mw_need_dest = true
	else this.__mw_moving = false end
	return false
end

if this.__mw_last_move_ts ~= store.tick_ts then     -- 同一 tick 只推一次
	this.__mw_last_move_ts = store.tick_ts
	U.walk_off__accel__unsnapped(this, store.tick_length)
	m.speed.x, m.speed.y = 0, 0                      -- 清掉，避免其他逻辑读到
end
return true
```

**引擎事实**：

- `all/systems/` 里**没有 motion 系统**：位移完全由实体自己的 main_script 逐帧推，`walk_off__accel__unsnapped` 不会双重推进。
- `main_script:on_update`（all/systems/main_script.lua:86）用**协程**跑 `s.update`（`main_script.type = 0` 默认、`runs = 1`），塔脚本天然是 `while true do ... coroutine.yield() end`。
- `last_hook:on_insert_unconditional` 会设 `motion.real_speed = motion.max_speed`，但它在 `main_script.insert` **之后**跑 → insert 里要自己先置 `this.motion.real_speed = this.motion.max_speed`。
- `U.animation_start` 第 5 参是 **loop**；`loop=true` 时不会重置 `a.ts`/`a.runs`，所以每帧重复调用是安全的（可用来持续修朝向），`loop=false` 才会重置 → 射击动画必须 `false`。
- 塔一般**没有行走动画**，位移期间用 idle 的朝向敷衍即可（`animation_name_with_direction(..., "idle", dx, dy)`）。

## 四、出售与塔位：两条路线（2026-09 定稿）

`all/systems/tower.lua:174`（on_update 轮询 `store.towers`，见 `e.tower.sell / e.tower.destroy` 标记就执行）会 `E:create_entity(e.tower.terrain_style)` 在原地重建一个塔位实体并插回场景 —— 移动过的塔（塔位已在首次移动时恢复）再卖，等于凭空多出一个免费建造位。

**路线 A：玩家塔保持可售 → 出售接管钩子**（movable_wild_magus 现行方案）：
- 首次移动 `restore_holder()` 恢复塔位后**不设** `can_be_sold = false`，保留 `__wm_holder_restored` 标记；
- hook `tower.on_update`（`require("all.systems.tower")`，幂等安装 + `simulation.init` 每关兜底）：每帧扫 `store.towers`，把 `__wm_holder_restored and (tw.sell or tw.destroy)` 的塔**摘出来**（`store.towers[id] = nil`）自己处理 —— 复刻 tower.lua:160-210 的退款（`wave_group_number == 0 and tw.spent or km.round(tw.refund_factor * tw.spent)`）、`_applied_mods` 清理、`queue_remove_entity`、`signal.emit("tower-removed", e, nil)`（成就处理器只用第一参，nil 第二参安全）、dust 特效、音效，**唯独跳过塔位重建**；其余塔照走原函数；
- 未移动过的塔不带标记 → 原版流程，零影响。
- ⚠ **`store.towers` 是"塔位+塔"混表**：任何遍历它做替换/重建的功能都会把移动塔误当塔位处理，
  都要做同样的"摘出 → 调原函数 → 放回"拦截。已知两处：`game_gui:build_random_towers`（随机塔按钮，
  `game_gui.lua:834`）和 **`CriketMenu:button_callback`（F1 快速建造菜单，`game_gui.lua:7927`，
  默认覆盖模式换掉所有 `ui.can_click` 条目）** —— 上一轮只拦了前者，用户实测立刻抓到后者。

**多塔通用化（2026-09 定稿，config 驱动）**：
- `movable_wild_magus_config.lua` 的 `towers = { {template=..., enabled=..., speed=...}, ... }` ——
  每种可移动塔一项：是否启用、移速（像素/帧，FPS=30）。
- 模板改造按 config 循环（逐塔 pcall，错误收集到 `templates.errors`）；
  `templates.movable_types[tower.type]` 集合生成后，wm_move 点击校验按集合判断（不再写死单塔）。
- 攻击脚本两档：`scripts.updates[template]` 有专用复刻（wild_magus，逐行复刻原版 update +
  refresh_tpos 每帧 + y_move_wait/y_move_anim_wait，真"边走边打"）；没有的走 `scripts.make_wrapper`
  通用包装 —— 前提是原版 update 里 `tpos(this)` 全是**现调**（非协程开头快照）：把原版 update 放进
  子协程，静止时每帧 resume、移动时冻结（tick_ts 继续走，蓄力/光束等待窗口恢复后自愈），到站恢复。
- **新增塔先做可行性判定（ray 的教训）**：关键不是"子弹跟不跟随"，而是**有没有持续引导光束
  （起点钉死数秒）**——
  - 短命弹丸（ray_duration 亚秒级、发射时 from=当下 this.pos）出膛后锚在发射点是正常弹道表现，
    不需要跟随修复。电涌巨像 `tower_sparking_geode_lvl4` 就是这种：普攻闪电段 hit_time=fts(3)、
    ray_duration=fts(16)≈0.53s 自删（tower_scripts.lua:18830）、track_target=false；索敌原点全
    tpos(this) 现调（:18383 的 update）→ wrapper 档直接适用，已实装（speed 1.5）。
  - 持续引导光束（如诡术魔导师 ray：单道光束 4s+，渲染起点=弹丸 this.pos 出弹快照，
    tower_scripts.lua:11587 update_sprite 只算角度/长度不更新起点）才是死穴，wrapper 档修不了
    （弹丸是独立实体，冻结塔协程不影响它），要么复刻弹丸脚本做起点跟随、要么放弃。用户已决定
    ray 不做。
- insert/remove：模板没有的补通用版（nav 初始化，`ensure_nav` 惰性），有的保留原版。
- 菜单注入按 `tmd[tt.tower.type][1]` 循环，统一 place 3（wild_magus 页空着；sparking_geode 页
  place 6/7 被技能占用、place 3 空闲；注入前先 grep 该页现有 place）。
- move_step 朝向精灵 id 取值链 `render.sid_shooter or render.sid_mage or render.sid_geode`（per-塔
  定义，都没有就跳过动画；geode 的 sprite[5].name="idle" 无 angles 表，
  `U.animation_name_with_direction` 会安全回退 idle+水平翻转）。

**塔名对照（易混淆，用户纠正过）**："诡术魔导师"= **`tower_ray_lvl4`**（tower.type="ray"、菜单页键
`ray`、脚本 `scripts.tower_ray`（tower_scripts.lua:10954）、i18n TOWER_RAY_*、KR5 塔）——**不是**
`tower_high_elven`（那是"高等精灵法师"，TOWER_HIGH_ELVEN_NAME，脚本 tower_scripts.lua:2406）。

**路线 B：赠送塔直接禁售**（地图内赠送塔适用，Tropical_Loop 方案）：
- `tt.tower.can_be_sold = false`（`TowerMenu:show` 也有一层 `not can_be_sold` 保护）；
- 克隆菜单页时过滤掉 `tw_sell`。

## 五、塔菜单注入自定义按钮

```lua
local tmd = require("kr1.data.tower_menus_data")        -- 注意：data. 前缀解析到 kr1/data/
local tpl = require("data.tower_menus_data_templates")
local M = require("kr1.data.tower_menus_data_scripts").merge   -- = table.merge(t1,t2,true)，会深拷 t1

local vanilla = tmd.wild_magus and tmd.wild_magus[1]   -- [type][level]
local page = {}
for i = 1, #vanilla do
	local item = vanilla[i]
	if item and item.action ~= "tw_sell" then page[#page + 1] = table.deepclone(item) end
end
page[#page + 1] = M(tpl.rally, {
	action = "mw_rally",           -- 自定义 action
	action_arg = nil,
	halo = "glow_ico_sub", image = "sub_icons_0001",   -- 复用 rally 模板图标（gui_ico 常驻图组）
	place = 3,
	tt_title = _("..._RALLY_NAME"), tt_desc = _("..._RALLY_DESCRIPTION"),
})
tmd["mobile_<x>"] = {page}         -- 关键：注册 type 对应的页
```

- `TowerMenu.button_callback`（game_gui.lua:8449）按 `item.action` 分发，**未知 action 是 no-op**，用 HOOK 接管即可：

```lua
function hook.TowerMenu.button_callback(cb, self, button, item, entity, mouse_button, x, y)
	if item and item.action == "mw_rally" then
		-- ... set_mode / 清 waypoints
		button:disable(); self:hide()
		return
	end
	return cb(self, button, item, entity, mouse_button, x, y)
end
```

- `TowerMenuTooltip:show` 只认 `tw_upgrade / upgrade_power / tw_buy_* / tw_unblock / tw_repair / tw_sell / tw_change_mode`，**其余 action 一律 `self.hidden = true`** → 自定义按钮借用 `tw_repair` 分支转发（该分支只读 `tt_title` / `tt_desc`）：

```lua
show(self, entity, {action = "tw_repair", tt_title = item.tt_title, tt_desc = item.tt_desc})
```

- **菜单类钩子必须延后安装**：插件在 `main.lua:263` 紧随 director 初始化，早于 game_gui 加载，此时 `TowerMenu`/`TowerMenuTooltip` 是 nil（HOOK 到空对象会打日志）。
  → 写一个幂等的 `install_menu_hooks()`（`pcall(require,"game_gui")` + `type(TowerMenu)=="table"` 检查），在 `simulation.init` 里调用（关卡开始 game_gui 必已加载），`hook:init` 里再兜底调一次。

- `upgrade_power` 按钮依赖 `entity.powers[item.action_arg]`（`level`/`max_level`/`changed`/`price_base`/`price_inc`），派生模板已继承，无需额外处理。

## 六、开局赠礼的时机

`simulation:init(store, system_names)` 时 `store.entities` 刚建好，关卡实体（含塔位）是 `LU.queue_insert` **排队**插入的 —— 要到第一次 `do_tick` 的批量插入阶段才进 `store`。

**插件版**：在 `hook.simulation.do_tick` 里延时召唤：

```lua
function hook.simulation.do_tick(next, self, dt)
	next(self, dt)                       -- 先跑完整 tick
	local store = self.store
	if not store or not store.__mw_spawn_armed or store.__mw_spawned then return end
	if not store.game_gui or not store.level then return end     -- 编辑器等非战斗场景不赠礼
	if (store.tick_ts or 0) < (store.__mw_spawn_at or 1) then return end   -- 等 1 秒
	-- spawn_mobile_magus(store)  → simulation:queue_insert_entity(e)
end
```

**地图版**（`level:update` 里，见 §九）：不用全局钩子，直接把等待写成协程
（`while store.tick_ts < wait_end do coroutine.yield() end`），**但必须放在关卡脚本的主等待循环之前**。

- `simulation:init` 钩子里置 `store.__mw_spawn_armed = true; store.__mw_spawn_at = cfg.spawn_delay or 1`，并 `store.__mw_spawned = nil`。
- 出生点优先取**塔位的 `tower.default_rally_pos`**（关卡作者标好的、军营士兵集结用的可行走地面），兜底 `P:node_pos(1,1,1)` + 偏移。`default_rally_pos` 默认是 `v(0,0)`，要跳过零值；`pairs` 顺序不稳定，要按 `holder_id` 排序取一个固定值，否则每次开局落点都不同。
- 找不到落脚点要设一个超时（如 tick_ts > 15）放弃，避免每帧重试。
- 登场音效由 `sound_events:on_insert_unconditional` 自动播 `sound_events.insert`，不需要自己 S:queue。

## 七、底座：**先修 name 再 hidden**（两步都要做）

塔的 `render.sprites[1]` 就是塔位底座（原版 `tower_wild_magus` 是 `terrain_mage_%04i`，`kr1/mage_towers.lua:1025`；`tower_holder` 是 `build_terrain_0001`，`kr1/foundamental_towers.lua:46`）。移动塔脚下挂一张塔位图很难看（玩家描述为"脚下有个空塔位贴图"）。

⚠ 两个坑要一起解决：

1. **`terrain_mage_%04i` 是字面量占位符**，图集里没有这个名字 → 渲染时 `I:s` 按字面查会刷
   `Sprite terrain_mage_%04i was not found`。光 `hidden = true` 不一定能消掉这条报错
   （取决于渲染链路的查表顺序），要先把 name 换成**真实存在**的底图名。
2. **光 `set_terrain_style` 不解决问题**：它（`all/utils.lua:3425`）只把 `sprites[1].name` 换成
   `build_terrain_xxxx`，底座照样显示。

正确做法是**两步都做**：

```lua
local U = require("utils")
local style = store.level_terrain_style          -- 本关没写顶层 level_terrain_style 时会是 nil
if type(style) == "string" then
	pcall(U.set_terrain_style, e, style)          -- 先把 %04i 占位符换成真实底图名
	e.tower.terrain_style = style
end

local base = e.render and e.render.sprites and e.render.sprites[1]
if base then base.hidden = true end               -- 再不画出来
```

- **⚠ `store.level_terrain_style` 可能为 nil**（自建关卡的 `_data.lua` 不一定写顶层 `level_terrain_style`；
  Tropical_Loop 就没写）。更稳的来源是**塔位自己**：`e.tower.terrain_style = "tower_holder_grass"`，
  从你选中的那个塔位实体上读，再传给 `set_terrain_style`。
- `set_terrain_style` 内部对 `name` 含 `%%` 的直接替换就 `return`（不走后面"坏塔位不改 sprite"的分支），
  所以用 `pcall` 包一层更安全；它同时会写 `e.tower.terrain_style`（出售流程要用，本塔已禁售）。
- `hidden` 是精灵的标准字段（`all/components.lua:195` `sprite.hidden = nil`），渲染层 `all/render_utils.lua:61/337` 用 `if not f.hidden then` 跳过 → 设为 `true` 即永久不画。
- 必须在 `simulation:queue_insert_entity(e)` **之前**设置，实体入队后才渲染，不会闪一帧。
- 该塔不会响应 `U.sprites_hide/sprites_show`（那些都是给敌人/英雄/召唤物用的），所以 `hidden = true` 不会被别的逻辑还原。

## 八、其他已实证结论

- **选中判定是纯矩形命中**：`U.find_entity_at_pos(store.entities_with_ui, x, y)` 只比 `ui.click_rect`（塔基础模板 80×70），**不需要 nav_mesh** → 不在塔位上的自由塔照样能点中。
- **敌人不会围攻它**：阻挡只认 `blocker.soldier.target_id` / `blocked.enemy.blockers`，塔没有 soldier 组件 → 永远不会被当阻挡目标（符合塔语义）。
- **法师精通（mage_brilliance）** 等按模板名查表的科技（`tower:on_insert_unconditional` 里 `mage_tower_map[entity.template_name]`）**不会把自建模板算进去** → 既不吃加成也不改动原版计数，正好满足"不影响原本的塔"。
- `tower.blocked = true`（boss 技能/关卡脚本批量锁塔）会让原版 update 走空分支 → 塔停止攻击；自建塔不在关卡的 towers 名单里，一般不会被点到。
- 图集：复用原版塔的贴图无需新资源（`terrain_mage_*`、`mage_towers_layer*`、`bolt/ray_wild_magus` 都在常驻图组）；`glow_ico_sub` / `sub_icons_0001` 在 `gui_ico` 常驻组。

## 九、部署形态：独立插件 vs 地图内实现（"只在哪张图生效"）

想清楚这个再动手，否则会出现"每张地图都白送一座"。

### 独立插件为什么是全局的（两个叠加的原因）

1. **模板注册被永久烘进 `entities_backup`**。`all/entity_db.lua:28-35`：

```lua
if not self.entities_backup then
	self:load()                                  -- ← 插件的 E.load 钩子在这里面跑
	self:precompile()
	self.entities_backup = quickcopy(self.entities)   -- 快照含刚注册的模板
else
	self.entities = quickcopy(self.entities_backup)   -- 之后每次都从备份还原
end
```

   `HOOK(E, "load", ...)` 里 `load(self)` 之后再 `RT()` → 注册发生在快照**之前**
   → 模板进备份 → **每张地图每次开局都被还原出来**。
2. **赠礼是游戏级全局钩子**：`simulation.init` 无条件 `store.__mw_spawn_armed = true`，
   `simulation.do_tick` 到点就送，唯一的判断只是"编辑器等非战斗场景不赠礼"。

→ 插件版**没有任何地图白名单**，想限制就得自己加（读 `store.level_name` / `custom_map_entry`）。
（`entities_backup` 只在内存里、`precompile` 不落盘、全仓无持久化缓存 →
停用插件立刻生效，不用清缓存。）

### 地图内实现：作用域由注册时机天然界定

把同样的东西搬进关卡插件（如 `mods/local/Tropical_Loop/`），**注册改到 `level:init`**
（它在 `E:Load()` **之后**，`all/systems/level.lua:72-79`）：第一次 Load 时备份已建好，
此刻注册的东西**不进快照**，而之后每次开局的 `quickcopy(entities_backup)` 都会把它还原掉
→ **只有本关有**，不需要任何判断。

推荐的文件切法（每个地图插件一份，互不影响）：

```
<map>/mobile_magus.lua            总装：文案 + 菜单页 + 菜单钩子 + 找落点 + 赠礼（对外 setup/grant）
<map>/mobile_magus_templates.lua  register()：RT/AC 注册塔与弹丸（幂等：E:get_template 有就跳过）
<map>/mobile_magus_scripts.lua    运行脚本（insert/update/remove/get_info）
<map>/mobile_magus_config.lua     可调参数（移速/赠送数/延迟/兜底偏移）
<map>/assets/strings/zh-Hans.lua  文案
```

- require 走 `<map>.<file>`：`plugin_main.lua` 给 searcher 加了 `plugins/?.lua`，所以
  `require("Tropical_Loop.mobile_magus")` → `plugins/Tropical_Loop/mobile_magus.lua`。
- 关卡脚本里接两处：`level:init → MM.setup(store)`、`level:update → MM.grant(store)`。
- **⚠ `grant` 内部会 `yield`**（等 `spawn_delay` 秒让塔位插入完再取集结坐标），
  必须排在 `while not store.waves_finished ...` 主循环**之前**，否则关卡结算逻辑被推迟。
- **菜单钩子可以在 `level:init` 直接装**：`director.lua:442` 在进游戏前就 `_require("game_gui")`，
  而 level:init 更晚，`TowerMenu`/`TowerMenuTooltip`（`game_gui.lua:7978/8639` 的顶层 `class(...)`）那时已存在
  —— 不像插件版（plugin 主控在 director 初始化之前）需要延后到 `simulation.init`。
  但 `hook_utils.HOOK` **不幂等**（只 append），必须用模块级 flag 防重复；钩子只在
  `item.action == "mw_rally"` 时生效，留在全局对其他地图无害。
- 落点用塔位的 `tower.default_rally_pos`，**按 `holder_id` 排序取最小**（`pairs` 顺序不稳定 → 落点随机）。
  底座样式读**那个塔位自己的 `tower.terrain_style`**（地图 data 常不写顶层 `level_terrain_style`）。
- **不需要声明图集/音效**：塔用的是常驻资源 —— `all/game.lua:30` 的 `game.required_textures`
  已含 `go_towers_group1..25+` + `tower_holders`，`sub_icons_0001` / `glow_ico_sub` 在 gui 常驻组。
  （这也是插件版 `assets/` 下只有文案、没有图片的原因。）
- 静态校验（语法校验查不出这些）：`.workbuddy/verify_tropical_mobile_magus.py` —— 相对 require 路径
  是否真的存在 / 关卡脚本调用的 `mobile_magus.*` 接口是否都有 / 是否残留指向独立插件的 require /
  两份 config.lua 是否都已 `enabled=false` / 塔位是否带 `default_rally_pos` / 模板名与 `tower.type` 一致 /
  **`grant` 是否在主循环之前**。

### ⚠ 插件版主控：顶层只 require 引擎基础库（踩过的坑）

插件 chunk 由 `plugin_main.lua:31-46` 的 `pcall(FS.load(chunk))` 加载，**失败只 log.error、不打断游戏**
→ 症状是"按钮不出现、塔和平常一样"，且游戏日志只在控制台、事后无法查。

主控顶层 `require` 了 templates（连带 scripts → `utils` → `path_db`/`grid_db`/`kr1.game_settings`/`seek`、
`sound_db` → `dove_modules.perf`）时，在 `main.lua:263`（director 刚 init）的早期时序下该链任一环抛错
= **整个插件静默死亡，一个钩子都没挂上**。旧插件 `mobile_wild_magus.lua` 对 `path_db` 专门
`pcall(require, ...)`、并把 templates/scripts 的 require 推迟到 `E.load` 钩子内 —— 就是踩过这个坑。

正确写法（`movable_wild_magus` 已验证）：
- 顶层只留 `all.constants` / `hook_utils` / `entity_db` / `i18n` / `lib.klua.log`（这些是引擎基础库，安全）。
- templates/scripts 改在 `apply_template_changes()` 内（E.load 钩子里、`E:get_template` 探测到模板库就绪后）
  `pcall(require, "...")` 再调 `templates.modify()` / `inject_menu_button()`。
- **⚠ `game_gui` 没有全局变量**：`game_gui.lua:83 local game_gui = {}` + 文件尾 return —— HOOK 它的函数
  （如 `build_random_towers`）必须 HOOK 在 `require("game_gui")` 返回值上，wrapper 内也要
  `require("game_gui").game` 取游戏引用；引用全局 `game_gui` = nil（HOOK 报"空对象"、运行时 index nil）。
  真全局 class 只有 `TowerMenu` / `TowerMenuTooltip` / `CriketMenu`（同一文件内 `class(...)` 无 local 前缀）。
- **加自证文件日志**：`io.open(love.filesystem.getSaveDirectory() .. "/<plugin>_debug.log", "a")` append
  （存档目录是 ASCII 路径，无 936 编码问题），打点 init / E.load / modify / inject / 菜单钩子安装 /
  按钮点击，每个失败分支落 `FATAL <阶段>: <err>`。日志文件全空 = 顶层 chunk 还在炸；有 FATAL 行 = 直接定位。
  （实测：第一轮就是靠它一眼定位的。）
- **⚠ log 必须点号调用**：`lib/klua/log.lua:129` 的方法是 `function newlog.error(fmt, ...)`（点号定义、
  不带 self）—— `log:error(...)` 冒号调用会把 log 对象当 fmt 传给 `strformat` → `bad argument #1 to
  'strformat' (string expected, got table)`，错误分支自身崩溃还会把整个 E.load 钩子链打断（引擎标准写法
  是 `log.error("... %s", tostring(x))`，见 `all/achievements.lua`）。
- **⚠ 模块文件用 `function xxx.fn()` 前必须有 `local xxx = {}`，末尾必须 `return xxx`** —— 两者缺一都是
  require 阶段 `attempt to index global 'xxx' (a nil value)` 或拿到 nil（这次 templates 文件就同时犯了）。

其他已排除的疑点（排查时容易误判）：全局 `bor` 存在（`plugin/plugin_globals.lua:34`）；`AC` 也在
plugin_globals；`E:get_template` 存在（`entity_db.lua:435`）；塔菜单数据是点塔时动态读
（`game_gui.lua:8210` `tower_menus_data[entity.tower.type]`）→ E.load 时机注入有效；按钮创建遍历
`tm` 全部条目（`game_gui.lua:8239`）→ 注入执行了按钮必现；`hook:init` 经
`xpcall(loaded_plugin.init, h, loaded_plugin, plugin_data)` 调用（init 抛错会进 `PLUGIN_ERRORS`
→ `error(PLUGIN_UI_INIT_ERROR)` 弹窗，而顶层 chunk 炸是纯静默——两者症状不同，可用来二分定位）。

## 十、交付与验证

1. 开发副本 `KingdomRushDove/mods/local/<entry>` → **必须复制**到 `%APPDATA%\LOVE\kingdom_rush_dove\plugins\<entry>`（那里是真目录、非软链；`plugin_paths.LOCAL_PLUGINS_DIR = "plugins"`）。改完 `diff -r` 两处确认一致。
2. 单插件启停看各自 `config.lua`（`enabled`），`plugins/plugin_main_config.lua` 只有 `{enabled = true}` 总开关。`config.lua` 建议带 `game_version = {"kr1"}`（启动器元数据，插件运行时不读）。
3. 语法校验：`python .workbuddy/lua_syntax_check.py <lua 文件...>`（用游戏自带 lua51.dll 真编译，把工作区与 AppData 两份一起传，顺带确认同步）。
4. 进游戏实测清单：开局是否出现；塔菜单是否显示两个技能按钮 + "调集"（**无出售**）；点"调集"再点陆地是否走动、速度是否 ≈75px/s；移动中是否照常开火（弹幕从当前位置发出）；**脚下没有塔位底座贴图**；原版可建造的狂野魔术师是否完全正常。
