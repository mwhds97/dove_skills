---
name: kr-dove-offline-lua-harness
description: 用《王国保卫战 Dove 版》自带的 lua51.dll（LuaJIT 2.1）在**不开游戏**的情况下离线跑引擎代码、验证插件逻辑——加载真 entity_db、真模板、真 scripts，对自定义模板/科技/波次做断言。含 ctypes runner、love 打桩用法、中文路径与 require path 的坑、「插件模板必须挂在 hook.E.load 之内才进 entities_backup」这类会让测试假阴性的时序陷阱，以及**动画键 / 帧名的离线校验**（引擎算键 = `prefix.."_"..name`，查不到只 log.error 后渲染成隐形、不崩 ⇒ 只能靠这套工具提前抓；含 size_names/size_prefixes/运行时补前缀等四类间接与"复数 animations 优先"两条语义）。触发词：离线验证插件、不开游戏测 Lua、lua51.dll、LuaJIT 跑游戏代码、entity_db 离线加载、love_stub、验证科技是否生效、动画键未注册、animation not found、素材隐形、帧名查不到、check_kr6_anim_keys。
agent_created: true
---

# Dove 插件离线验证（lua51.dll + ctypes）

已验证案例：`johnny_deadeye` 的「英雄弹丸吃箭塔弹丸类天赋」——43 项断言全绿，
其中「幂等」「不覆盖第三方 main_script.insert 包裹」「跨关标记清空」这类结论**只有跑真引擎才能证**。

## A. 为什么需要它 / 边界

- 本机没有 `luajit.exe`，但**游戏根目录有 `lua51.dll`**（实测 `LuaJIT 2.1.1700008891`）。
  用 Python `ctypes` 驱动它，就得到一个能跑真 Lua 的解释器。
- `KingdomRushDove/scripts/ci/love_stub.lua` 已经把 `love.*` / `image_db` / `animation_db` / `sound_db`
  等打成空实现，于是 `require('entity_db')` + `E.Load()` 能在纯 LuaJIT 下跑通
  （`scripts/ci/check_text_expr.lua` 是官方示例）。
- ⚠⚠ **`love_stub.STUB_MODULES` 里的 `animation_db` / `lib.klove.image_db` / `sound_db` 是「假表」**：
  它们被顶成「`__index` 一律返回 no-op 函数」的代理表 —— 连 `type(db.fn) == 'table'` 之类判断都会**假阳性**。
  **想读真 db 必须先清缓存**：
  ```lua
  package.loaded['animation_db'] = nil;  package.preload['animation_db'] = nil
  local A = require('animation_db')      -- 现在才是真 animation_db
  ```
  ⚠ 但 `image_db` / `sound_db` 清缓存后**也会崩**（它们依赖 love.graphics / love.audio 的真实资源）。
  ⇒ 这两个要**自造真表**：插件的 `prevent_missing_resource_errors()` 会对 `I.atlas_uses` 调
  `setmetatable`，拿到 no-op 函数就崩 → 至少给 `I.atlas_uses = {}`、`I.db_atlas = {}`。
- 适合：验证模板注册/科技作用面/脚本分支/配置映射/**幂等性**。
  不适合：渲染、音频、真实战斗节奏（那些只能进游戏看）。

## B. Runner

`run_lua.py`（本技能包内，项目里也放了一份在 `<项目>/.workbuddy/run_lua.py`）：

```bash
python <skill>/run_lua.py <游戏目录> <.lua 脚本> [args...]
```
（`<skill>` = 本技能包目录；`<游戏目录>` = `<工作区>\王国保卫战Dove版\KingdomRushDove`。用 managed venv 时把 `python` 换成 `%LOCALAPPDATA%\..\.workbuddy\binaries\python\envs\default\Scripts\python.exe`，非必须 —— 纯标准库。）

关键设计（都是踩出来的）：

| 问题 | 处理 |
|---|---|
| 本机没有 luajit 可执行文件 | `ctypes.CDLL("lua51.dll")` + `luaL_newstate/luaL_openlibs/luaL_loadbuffer/lua_pcall` |
| 脚本路径含中文（工程目录名「王国保卫战Dove版」）→ Lua 的 `fopen` 走 ANSI 打不开 | **脚本内容由 Python 读进来交给 `luaL_loadbuffer`**，chunkname 只用相对路径；同时 `os.chdir` 到游戏目录，让 `require` 的相对路径由 Windows 内核按 CWD 解析 |
| `version.lua` 读全局 `arg[0]` | pcall 前先 `arg = { [0] = ... }` |
| `lua_pushcfunction` 不是导出符号 | 别声明它（它是宏） |

## C. 被测脚本的固定开头

```lua
package.path = './?.lua;./kr1/?.lua;./all/?.lua;./lib/?.lua;./kr1-desktop/?.lua;'
	.. './all-desktop/?.lua;./_assets/?.lua;./_assets/kr1-desktop/?.lua;'
	.. './mods/local/?.lua;./mods/local/<entry>/?.lua;'  -- 插件自己的模块
	.. './plugin/all/?.lua;'                             -- hook_utils 在这（游戏里由插件加载器加进 path）
	.. package.path

require('scripts.ci.love_stub')      -- 打桩副作用
local E = require('entity_db')
local hook_utils = require('hook_utils')

-- ⚠ 本体模块在「模块级」就会调 _()，i18n 必须先装语言包，否则报
--   all/i18n.lua:41: attempt to index local 'l' (a nil value)
require('i18n').load_locale('zh-Hans')
```

## D. 三个会让测试**假阴性**的时序陷阱（一定要照做）

1. **不要用 `love_stub.load_entity_db()`**：它内部就 `E.Load()` 跑掉了，
   此时 `entities_backup` 已生成 → 插件模板永远进不去备份 → 之后任何 `E:Load()` 都会把模板清掉。
   正确姿势是**先装钩子再自己调**：

   ```lua
   hook_utils.HOOK(E, 'load', function(next, self)
       next(self)
       require('<entry>.scripts.hero_scripts')
       require('<entry>.scripts.hero_templates')   -- 复刻插件的 hook.E.load 时序
   end)
   pcall(E.Load, E)
   ```
   这样 `entities_backup` 才含插件模板，才能测「跨关重建」这类行为。

2. **`entity_db.load` 整个进程只跑一次**（`entity_db:Load()` 首次才走 `self:load()`）。
   想测"每次 `E:Load()` 都重新执行 X"的东西，先确认它挂的是 `E.load` 还是别的点。

3. **第二关的状态要真的走一遍 `E:Load()`**：它是 `table.clear(entities)` + 从 `entities_backup` 深拷贝，
   挂在模板上的自定义标记会自然消失 —— 幂等设计经常就靠这一点，值得专门断言。

## E. 用技术手段替代「跑不动的真函数」

`scripts.shotgun.insert` 之类需要 `pos/from/to` 等运行时字段，离线直接调用会崩。
**用哨兵函数替换它**，既可以跑通包裹链，又能数出"被包了几层"：

```lua
local calls = 0
local function sentinel(this, store) calls = calls + 1 return true end
E:get_template('my_bullet').main_script.insert = sentinel

-- patch 之后，用假 store + 飞行目标调一次，读倍率就知道叠了几层
local fake_store = { entities = { [1] = { id = 1, vis = { flags = F_FLYING } } } }
local this = { bullet = { target_id = 1, damage_factor = 1 } }
E:get_template('my_bullet').main_script.insert(this, fake_store)
print(this.bullet.damage_factor)   -- 1.25 = 只 1 层；1.5625 = 叠了 2 层
```

同理，测"科技/天赋是否施加"时直接伪造 `UP.list` / `UP.max_level` / `UP.levels`：

```lua
UP.list = { [1] = merged_talents }   -- 可把 4 张科技表的 archers 项并成一张
UP.list_id = 1
UP.max_level = 6
UP.levels = setmetatable({}, { __index = function() return 6 end })
UP:patch_templates(6)
```

## E-bis. 跑实体 `update`（永续协程）—— 两个必做桩

想在离线环境里驱动英雄/塔的 `update` 走完一整轮逻辑（例：真的触发一次技能施放，
看它有没有给经验），只搭 `E.Load` 是不够的，还要处理两件事：

1. **每步把 `render.sprites[*].runs` 推高**（最关键）。
   离线桩不跑动画系统，`runs` 恒为 0，而 `U.y_animation_play`
   （`all/utils.lua:788`）是 `while a.runs <= times do coroutine.yield() end`
   —— 会**永久挂住**。症状很有迷惑性：协程一直 `suspended`、帧号在涨、
   但协程里任何 `print` 都不输出，看起来像"逻辑没走到"。
   ```lua
   local function bump_anims(ent)
       for _, s in pairs(ent.render.sprites) do
           if type(s) == 'table' then s.runs = (s.runs or 0) + 100 end
       end
   end
   -- 主循环里：store.tick_ts = store.tick_ts + 1; bump_anims(hero); coroutine.resume(co)
   ```

2. **`this.nav_rally` 不能是 nil**：主循环每帧读 `this.nav_rally.new`
   （例 `johnny_deadeye/scripts/hero_scripts.lua:303`）→ nil 直接崩。
   给哨兵：`hero.nav_rally = { new = false, pos = v(400, 300) }`。

**还要给齐的运行时字段**：`id` / `pos` / `health.dead=false` / `health_bar` 表 /
`render.sprites` **至少 2 项**（有的脚本读 `sprites[2]`）/ `unit.cooldown_factor` /
`unit.is_stunned` / `timed_attacks.list[*].ts` 设成很大的负值（让 CD 立刻就绪）。

**桩替换「选敌」这一层**：`U.find_enemies_in_range` / `U.find_foremost_enemy`
走 `all/seek.lua` 的空间索引（靠 `seek.set_id_arrays` 注入，离线必 nil 崩）。
用假函数返回自己造的敌人即可 —— 范围查询本身通常不是验证目标。

**崩了也可能是对的**：施法成功后协程会继续往下跑，那里常会碰
`all/simulation.lua:228` 之类的动画帧数（桩没有）→ 抛错。断言要在
`coroutine.resume` 返回 false 时**先查目标字段（如 `xp_queued`）再退** ——
崩在 resume 内部时，协程里已执行的赋值仍然生效。

## E-bis-2. ⭐ 「路标崩溃法」：证明"函数开头几行不再崩"，不必造完整 store

场景：真机报的崩点在某函数**开头几行**（例 `hero_zezitra` 的 `soldier_possessed_pet.update`
第 894 行 `store.count_groups[tac.count_group_type]`，其中 `tac = timed_attacks.list[2]` 为 nil），
而那个函数**整条跑不动**（要真 store / 动画 / 寻路）。造完整桩成本极高，但"改完还崩不崩"必须验。

做法：**把真函数丢进 `pcall`，并在崩溃行之后故意留一个"路标"字段缺失**：

```lua
local pet = E:create_entity("soldier_possessed_pet")   -- 用真实体（真组件）
pet.timed_attacks.list = {}            -- ⬅ 真机崩溃条件（0 条）
pet.render = nil                       -- ⬅ 路标：只有越过 ta/tac 两行，才会因 render 缺失报错
local fake_store = { tick_ts = 0, count_groups = {}, entities = {}, level_difficulty = 1 }
local ok, err = pcall(scripts.soldier_possessed_pet.update, pet, fake_store)

ck("list 为空时不再崩在 tac", ok or tostring(err):find("'tac'") == nil, tostring(err))
ck("（路标）确实越过了 ta/tac 行", (not ok) and tostring(err):find("render") ~= nil, tostring(err))
```

要点：
- **必须调用真函数**（`scripts.<x>.update`），别把逻辑抄进探针 —— 抄一遍就是同义反复的自证。
- 路标要选**紧跟崩溃点之后**才会被读到的字段，且错误文本里能出现它的名字。
- 断言写两条：① 错误里**不含**原崩溃关键字；② 错误里**含**路标字段（证明真的越过去了）。
- 与上文"崩了也可能是对的"同一思路（用"后方的崩"给"前方的通过"当证据），区别在于路标是**主动设计**的。

## E-ter. 源码结构断言要用 plain 查找

`string.find` 的第二个参数是 **Lua 模式**，`(` 会开启捕获，未转义的 `)`
匹配不上 → `s:find('f(x)')` **静默返回 nil**（看起来像"源码里没有这句话"）。

```lua
local idx = s:find('SU.hero_gain_xp_from_skill(this, skill)', 1, true)  -- ✅ plain
```

## E-quater. `io.open` 相对路径随 cwd 变

`run_lua.py` 会 chdir 到 `KingdomRushDove/`（为了绕开中文路径 ANSI 问题），
所以脚本里开游戏文件要用 `mods/local/...`，**不是** `KingdomRushDove/mods/...`
也不是 `../mods/...`。不确定时先探一下：

```lua
local f = io.open('probe_cwd.txt', 'wb'); f:write('x'); f:close()  -- 看文件落在哪
```

### E-quater-bis. ⚠⚠ 中文目录下的被测文件**读不进来** —— 先 cp 成 ASCII 副本

`mods/我的插件/arcane_archer_custom/arcane_archer_custom_config.lua` 这类**路径里带中文**的文件，
`io.open` / `require` 一律失败：Lua 把 UTF-8 字节原样交给 CRT 的 `fopen`，Windows 按 ACP(GBK) 解释 ⇒ ENOENT。
（能被 `require` 的是 `mods/local/` 这种纯 ASCII 段。⚠「相对路径不受代码页影响」这条**只在路径本身是 ASCII 时成立**。）

`require` 还会掩盖症状：找不到就是 `module not found`，看起来像"我 path 写错了"。

**做法**：Python 侧先复制成 ASCII 副本，再让 Lua 读 —— 顺便让探针能读**待测文件本身**做结构断言：

```bash
mkdir -p KingdomRushDove/_verify_tmp
cp "KingdomRushDove/mods/我的插件/<entry>/<file>.lua" KingdomRushDove/_verify_tmp/plain.lua
```

```lua
local function load_table(p)          -- 读 Lua 表文件（不 require，避开 package.path 与中文）
	local f = io.open(p, 'rb'); if not f then return nil, 'open failed: ' .. p end
	local s = f:read('*a'); f:close()
	local chunk, e = loadstring(s, '@' .. p)
	if not chunk then return nil, e end
	return chunk()
end
local cfg = load_table('_verify_tmp/plain.lua')
```

**跑完记得 `rm -rf KingdomRushDove/_verify_tmp`** —— 留在游戏目录里会被当成资源扫。

## E-quinquies. ⚠ 别 `require("scripts")` —— 会拖进整条引擎依赖链

想断言「引擎里有没有 `scripts.hero_basic.get_info` 这个函数」时，**不要** `require("scripts")`。
它会连带拉进 `all/kr5_taunt_balloon.lua` → `data.kr5_text_balloons`（离线缺这份资源）→ 直接崩：

```
all/kr5_taunt_balloon.lua:4: module 'data.kr5_text_balloons' not found
```

**改用源码结构断言**（读 `all/scripts.lua` 文本 + `plain` 查找）：

```lua
local engine = io.open('all/scripts.lua'):read('*a')
check(engine:find('get_info = scripts.soldier_barrack.get_info', 1, true),
      'hero_basic.get_info 指向 barrack 版')
check(not engine:find('get_info_melee', 1, true),
      'Dove 没有 get_info_melee（KR1 独有）')
```

**⚠ 陷阱**：`mods/local/资源/output/all/scripts.lua` 是**整份引擎源码备份，不被加载** ——
在里面 `grep get_info_melee` 会**命中**（`:1580`），很容易误判"Dove 有这个函数"。

**⚠ 反向陷阱（同样致命，实测踩过）**：备份与真源码**同名不同实现**时，先读备份会让你**建立起错误的模型**。
例：`all/script_utils.lua:783`（真）的 `hero_level_up` 净 XP = `xp_queued × store.hero_xp_multiplier`（**只一个乘数，取自 store 字段**），
而 `资源/output/all/script_utils.lua` 那份是 `xp_queued × expected_level_multiplier × difficulty_multiplier`（读 `GS.hero_level_expected*`）。
照备份写探针 ⇒ store 少了 `hero_xp_multiplier` ⇒ `:1039 attempt to perform arithmetic on field 'hero_xp_multiplier'`。
⇒ **凡是要断言/复现引擎行为，一律以 `all/`、`kr1/`、`all-desktop/` 下的真文件为准**；备份只作"历史差异"参考，
且**读之前先确认同名真文件存在**，两边不一致时信真的。

## E-sexies. ⚠ `love_stub` 的桩是「返回空函数的表」—— 会破坏「不存在则创建」

`love_stub.lua:44-55` 把 `STUB_MODULES` 里每个模块 `package.preload` 成同一个对象：

```lua
local stub_fn = setmetatable({}, { __index = function() return function() end end })
```

关键危害：**`__index` 返回的是 truthy 的空函数**，所以任何"字段不存在就创建"的写法全部失效：

| 代码 | 期望 | 实际 |
|---|---|---|
| `I.atlas_uses` 当表索引 | 表 | 拿到**函数** → `attempt to index field 'atlas_uses' (a function value)` |
| `local mt = getmetatable(I.atlas_uses) or {}` | `{}` | `getmetatable(fn)` 返回 function → 下一行 `setmetatable(fn, fn)` 崩 |
| `if not obj.__hooks then obj.__hooks = {} end`（`hook_utils.lua:82`） | 建表 | `obj.__hooks` 是 truthy 函数 ⇒ **不建表**，`obj.__hooks[fn_name]` 立刻崩 |

⇒ **修法：探针里用 `package.preload` 覆盖成「安全桩」**（同 key **后写者胜**，在 `require('scripts.ci.love_stub')` 之后、`require` 插件之前写）：

```lua
local TABLE_KEYS = { atlas_uses = true, persistent_textures = true,
                     groups = true, __hooks = true }
local function safe_stub()
	return setmetatable({}, {
		__index = function(t, k)
			if TABLE_KEYS[k] then local v = {}; rawset(t, k, v); return v end
			local fn = function() end; rawset(t, k, fn); return fn   -- 其余保持可调用
		end,
	})
end
for _, name in ipairs({
	'lib.klove.image_db', 'sound_db', 'animation_db', 'wave_db',
	'gg_views', 'game_gui', 'lib.klove.shader_db',
}) do package.preload[name] = safe_stub end
```

覆盖清单要**宁可多写**：凡插件里会被 `索引` 或 `HOOK` 的 stub 模块都要包进来
（漏一个就在那一行崩，且报错位置与真因相隔很远）。

**2026-10-03 zezMitra 移植补三条**：

1. **探针侧更根本的修法是给插件 guard 加 type 防护**（一次性、真机无害）：
   `prevent_missing_resource_errors` 里 `atlas_uses` / `S.groups` 先 `type(x)=="table"`
   再挂元表/建组，否则 stub 环境下 `setmetatable(fn, mt)` / `S.groups[名]` 直接崩在 hook.init。
2. **`E:clone_t(模板)` 在 stub 环境 = 段错误**（Python 端无 traceback，连 runtime error 都不打）
   ⇒ level_up 类探针**直接拿真模板当 this**（ember/zezitra 探针同款），别 clone。
3. **animation_db.extract_frame_from 返回值**：`def = {frame_count, prefix, nums(ffi uint32 数组, 0 基)}`
   ⇒ 取 `def[1]`（帧数）、`def[3][i]`（帧号）；**别写 `def[3].nums`**（cdata 无该字段 → nil 索引崩）。
   断言 ANIM_DEFS 时优先读 `A.db[k]`（真模块 register_animations 已写入），别断言入参定义表。

## E-septies. ⚠ 插件的启动链：`init()` 挂钩子 → **第一次** `E.Load()` 才注册模板

插件的 `HOOK(...)` 注册在 `hook:init(mod_data)` 里；而**模板注册**（`require hero_templates`）
在 `hook.E.load` 里，它被挂到 E 的 **小写 `load`**（`all/entity_db.lua:57 function entity_db:load`）上。

**`E.Load()`（大写）只在第一次走 `self:load()`** —— 第二次走 `entities_backup` 分支
（`entity_db.lua:36-42`）**不再调 load()** ⇒ 插件钩子不跑 ⇒ **所有插件模板都是 nil**。

⇒ 正确顺序（**先 init，再 Load，且只 Load 一次**）：

```lua
local hook = require('ember_hero.ember_hero')  -- ⚠ 模块常直接 return hook 本身
pcall(hook.init, hook, {})                     -- ① 挂钩子（含 E.load 上的模板注册钩子）
local ok, err = pcall(E.Load, E)               -- ② 首次 Load → 触发 → 模板注册
-- 不要在之后再来一次 E.Load：那是 no-op，且不会补注册任何东西
```

**症状对照**：如果顺序写反（先 `E.Load` 再 `hook.init`），`E:get_template('hero_ember')`
以及**所有**插件模板都是 `nil`（不是只有"你要测的那个"）——看到"全是 nil"就往这个方向查。

**判断模块返回什么**：看被 require 文件的 `return` 那一行。
`mods/local/ember_hero/ember_hero.lua:854` 是 `return hook` ⇒ 模块**就是 hook 表**，
写成 `hook.init(hook.hook, {})` 会拿到 `auto_table_mt` 造出的**空表** ⇒ `attempt to call a table value`（报错指向 `pcall` 那行，看不出真因）。
⚠ 反过来，`hero_scripts.lua` **没有 `return`**（末尾是 `log.info`）⇒ `require` 返回 **`true`**。
这类文件里的函数挂在**全局 `scripts` 表**上 ⇒ 要 `require('scripts').ember_hellfire_side_effect` 取，
不要 `require('ember_hero.scripts.hero_scripts').xxx`。

判断"引擎真实行为"只认 `all/`、`kr1/` 这些**实际搜索根**下的文件。

**⚠ 什么时候可以放心 `require("scripts")`**：当这个校验脚本**本来就要跑整套引擎**时
（已经 `E.Load` / 加载了 `entity_db`），依赖链早就拉全了，`require("scripts")` 不会更糟 ——
而它往往是**唯一**能拿到插件函数的途径（`hero_scripts.lua` 之类**没有 `return`**，
函数挂在全局 `scripts` 表上）。上面那条禁令针对的是「只想查一个字符串却在空环境里 require」的场景。

**⭐ `E.Load()` 之后可以遍历 `E.entities` 做"数据分布断言"** —— 当 bug 的根因是"原版代码假定了某数据形态，
而 Dove 的真实数据形态不同"时，这是最有力的证据（例：宠物 AI 假定 `timed_attacks.list` 有 2 条，
实测 380 个敌人里 298 个 0 条 / 73 个 1 条 / 仅 9 个 ≥2 条 ⇒ 必崩）。

```lua
local n_all, n_ok = 0, 0
for name, t in pairs(E.entities) do
    if type(name) == 'string' and name:sub(1, 6) == 'enemy_' and type(t) == 'table' and t.enemy then
        n_all = n_all + 1
        local list = (t.timed_attacks and t.timed_attacks.list) or {}
        if #list >= 2 then n_ok = n_ok + 1 end
    end
end
-- ✅ 断言「量级/比例」，别写死计数 —— 数据会随版本变（写入数字 = 下次假红）
check(n_all > 0 and n_ok * 2 < n_all, "敌人 timed_attacks ≥2 条的不足一半", n_ok .. "/" .. n_all)
```
字段/组件名写法与小抄（`t.enemy`、`t.health.hp_max`、组件的表被 `quickcopy` 深拷贝过来）见
`kr-dove-enemy-data`。

## E-octies. ⚠⚠ 「假绿」：脚本中途报错 + 只看输出尾部 = 全盘漏测

**2026-10-02 实测踩过，代价是从上一轮起整段校验静默瘫痪而没人发现。**

```lua
-- 第 181 行用了 B_bal ……
check(math.abs(vl.refund - B_bal.skills.volcano.refund) < 1e-9, ...)
-- ……
local B_bal = require('ember_hero.scripts.balance')   -- ← 第 257 行才声明
```

`local` **声明之前**的引用不是编译错误 —— Lua 把它当作**全局变量**（nil），
于是运行时炸在 `attempt to index global 'B_bal' (a nil value)`，
**脚本从第 181 行起当场中断**，后面的 C 尾段 / D / E 全部没跑。

要命的是**怎么发现的**：跑完用 `| tail -3` 看输出，看到的是最后几个 `PASS`，
**完全没有异常感**；用 `| grep FAIL` 更是干干净净（因为根本没跑到会 FAIL 的地方）。
于是"没有 ALL PASS"这个最关键的信息被 tail 掉了。

**纪律（三条，缺一不可）**：

1. ⭐⭐ **永远看退出码，不要只看输出**。`run_lua.py` 遇运行时错误会打印
   `[run_lua] runtime error: <文件>:<行>: <消息>` 并返回**非 0**。所以：
   ```bash
   python .workbuddy/run_lua.py KingdomRushDove <probe>.lua > /tmp/o.txt 2>&1; echo "EXIT=$?"
   ```
   ⚠ 别写成 `... | tail -3; echo $?` —— `$?` 拿到的是 **tail** 的退出码，永远是 0。
   要拿管道前的码就用 `${PIPESTATUS[0]}`，或干脆重定向到文件。
2. ⭐ **把成功也变成一条可断言的输出**：脚本末尾必须有显式的
   `ALL PASS` / `os.exit(1)` 分支，读结果时**同时**确认「EXIT=0」**且**「出现了 ALL PASS」。
   缺任何一个都当成失败。
3. ⭐ **`local` 一律就近提前声明**。所有 `require(...)` / 公共句柄集中放在文件**头部**，
   永远不要中途二次 `local` 一个同名句柄（哪怕"只是补一下"）。
   ⇒ 同一个模块重复 `require` 得到的**是同一张表**，多余的那次 `local` 只有坏处没有好处。

**顺带**：这类"中途中断"会让**旧断言永久失效**而表面一切正常 —— 所以
任何"改了被测代码"的动作之后，都要先确认校验脚本本身**跑满**了（对比 PASS 数量是否只增不减）。

## E-novies. ⚠ `re_farmer` 派生的自定义援军**必须覆盖 `main_script.insert`**

**2026-10-02 实测踩过**：`reinforcement_more_choice` 插件 1~4 号援军全部刷
`render.error animation <模板名>_2_idle not found`（`_2` 是随机数）。

**根因在 `kr1/game_templates.lua:481-486`**：
```lua
tt = RT("re_farmer", "soldier_militia")
tt.main_script.insert = fn_group(function(this, store)
    local i = math.random(1, 3)
    this.info.portrait = string.format("info_portraits_soldiers_%04d", this.info.portrait_idxs[i])
    this.render.sprites[1].prefix = this.template_name .. "_" .. i   -- ← 元凶
    return true
end, scripts.soldier_reinforcement.insert)
```
`re_farmer` 是**农民援军**，insert 会随机挑 1~3 号立绘并把 prefix 改写成 `<模板名>_<i>`。
插件 `E:register_t(x, "re_farmer")` 后 prefix 虽已正确复制成 `enemy_dark_knight`，
但**实体一跑 insert 就被改回** `reinforcement_more_choice_dark_knight_N`；
`all/systems/render.lua:398` 用 `prefix .. "_" .. name` 查动画库 → 查不到。
⇒ **模板上看 prefix 是对的，实体上才是错的** —— 只断言模板会假绿，必须 `create_entity` 后再断言。

**修法**：
```lua
e.main_script.insert = scripts.soldier_reinforcement.insert   -- 覆盖掉 fn_group 包装
```
（`re_farmer` 及其派生 `re_farmer_well_fed` / `re_conscript` / `re_warrior` / `re_legionnaire` 全都带这段。）

**副作用（可接受）**：援军不再随机换立绘，固定用插件自己指定的 `info.portrait`。

**通用诊断手法 —— sprite 字段的 `__newindex` 陷阱**（sprite 是普通 Lua 表不是 ffi，能挂代理）：
```lua
local sp = ent.render.sprites[1]
ent.render.sprites[1] = setmetatable({}, {
    __index = function(_, k) return sp[k] end,
    __newindex = function(_, k, v)
        if k == 'prefix' then print('WRITE -> '..tostring(v)); print(debug.traceback('', 2)) end
        sp[k] = v
    end,
})
pcall(ent.main_script.insert, ent, { tick_ts = 0 })
```
⚠ `__newindex` **只在 key 原先不存在时**触发，所以要**先 `sp.prefix = sp.prefix` 赋一次**再挂代理。
本例靠它一次定位到 `game_templates.lua:484` —— 静态 grep `prefix` 在 `all/` 里**完全搜不到**这段。

## E-decies. ⚠ 离线环境缺 `SU` / `F` / `GS` 等由 `plugin_globals.lua` 注入的全局

游戏里 `plugin/plugin_globals.lua:41` 有 `SU = require("script_utils")`。
离线不加载那个文件，于是插件脚本里 `SU.xxx` 会报
`attempt to index global 'SU' (a nil value)` —— **这是离线假阳性，不是真 bug**。
被测脚本头部手动补齐：
```lua
SU = require('script_utils')
```
判定方法：报错的行号落在**插件代码**里、而该变量在引擎里只被 `plugin_globals.lua` 赋值
⇒ 离线环境问题。同类还有 `F`（格式化）、`GS`（存档）、`simulation`。

⚠⚠ **反向误判（2026-10-02 实际犯过）**：静态阅读插件源码时，看到 `SU.xxx` 而该文件**没有**
`local SU = require("script_utils")`，**绝不能**下结论"这段代码在游戏里会崩"。
插件环境里 `SU` 是引擎注入的**真全局**，插件文件根本不需要自己 require。
判据：只要 `plugin/plugin_globals.lua` 里有这句赋值，`SU` 在任何插件脚本里都可用（`F`/`GS`/`simulation` 同理）。
本案：`reinforcement_more_choice/scripts.lua` 顶部只有 `entity_db` + `vector` 两个 require，
却直接用 `SU.y_soldier_melee_block_and_attacks` —— 这是**合法**的，不是 bug。
（顺带：`hook_utils` 也一样是全局可用的模块名，插件里 `require("hook_utils")` 照常能拿到。）

## E- undecies. ⚠ `run_lua.py` 的三个环境坑（2026-10-02 修正）

1. **`lua51.dll` 常常不在游戏目录里**，而在**它的上一级**（实测 `王国保卫战Dove版/lua51.dll`，
   而 `KingdomRushDove/` 里没有）。官方 runner 按「skill 目录的上一级」找，会报
   `FileNotFoundError: ...\skills\lua51.dll`。修法：依次找 `cwd` / `cwd 上一级` / `skill 上一级`。
2. **`arg[]` 传不进去** —— `run_lua.py` 自己 `os.chdir(cwd)` 并用 `sys.argv`，
   传给 Lua 的 `arg` 不可靠。**探针参数一律用 `os.getenv()`**。
3. **脚本路径要传绝对路径**：runner 先 `os.chdir` 再读脚本，传相对路径会 FileNotFoundError。

## E-duodecies. ⚠⚠ 探针里**手打引擎标识符必须字节校验**（2026-10-10 `sparking_geode` 实证）

探针要模拟引擎去查表（`tower_menus_data.sparking_geode`、`E:get_template("...")`、i18n 键……）时，
若标识符**手打**而不是从源码复制，一个字母之差就会让引擎侧**静默取到 nil**，于是：

- 引擎函数早退（例：`patch_tower_menus_data` 的 `local menu = tdata.sparking_geode` 为 nil ⇒ `return false`），
- 补丁**整段不生效**，而探针断言报出的是**完全无关的症状**（例："`tt_list` 是 nil"）⇒ 你会去查一个不存在的问题。

**识别信号（很好用）**：`rawget(t, k) == nil` 但 `pairs(t)` 能列出这个键 —— 说明**两个字符串的字节不相等**
（一个是源码里的真名、一个是你手打的假名）。`for k in pairs(a) do print(#k, table.concat({k:byte(1,-1)}, ",")) end` 对比即可确认。

**核对手法**（一条命令定音；`SPARKL?ING` 同时兼容少写/多写 `l`）：
```bash
grep -oE "SPARKL?ING_GEODE|sparkl?ing_geode" <各文件> | sort | uniq -c
```
本项目实测：全工程（插件 + `kr1/data/tower_menus_data.lua` + `kr1/engineer_towers.lua` + 本体 locale）
**只有 `sparking_geode`（无 `l`），零处 `sparkling`**。

⇒ 规则：**能从源码/`require` 读到的名字就别手打**；必须手打时（i18n 键、模板名、`action_arg`）
**先 grep 一次拿到真名再粘贴**。另外：被 `require` 的桩模块若用 `package.preload` 装，
查表前先断言"桩确实被拿到了"（例如 `check(t[1][1].tt_list ~= nil, "补丁拿到了菜单表")`），
否则拼写/键路径错误会伪装成业务失败。

## E-terdecies. ⭐ 验证「删除类改动」的探针三断言（2026-10-10 `sparking_geode_enhanced` 清理死代码实证）

删代码比加代码**更容易假绿**：语法过了、游戏也没崩，但你无法证明"该删的删了、不该删的还在"。
删完**必写**探针，且至少覆盖这三条：

1. **该消失的确认消失** —— 别只 grep 源码。用**运行期记录器**：把 `RT(name, parent)` 桩成
   `registered[name] = {...}`，跑完断言 `registered["<被删模板>"] == nil`。
   （纯 grep 只能证明"文本没了"，证明不了"注册也没了"。）
2. **不该消失的确认还在** —— 同一次运行里断言**真机制**仍注册 / 仍被挂钩：
   - 实体类：`registered["<真机制模板>"] ~= nil`；
   - **挂钩类最有效的一招**：桩里存住原函数引用，跑完断言 `tt.main_script.update ~= ORIGIN_AL_REF`
     ⇒ 直接证明"包装仍然装上去了"（比检查文本里有没有 `HOOK` 字样强得多）。
3. **幻键清零** —— 被删代码常引用过**从不存在的 config 键**。把那些键名写成 Lua 数组，
   逐个 `src:find(k, 1, true)`（plain，别用模式），断言全为空。
   顺便把「模板改造值」的断言**一并带上**（本例 14 条），一次运行同时覆盖"删干净 + 没删错 + 数值没跑偏"。

**桩的最小配方**（`templates.lua` 这类"注册模板 + 改数值"的文件）：
`package.preload` 装 `entity_db`（`get_template` / `create_entity` / `create_damage`）、`sound_db`、
`utils`、`game_templates_utils`、`all.constants`；`_G` 补 `RT/AC/CC/V/vv/vec_1/fts/FPS/Z_*/F_*/DAMAGE_*/queue_*`；
**假 `E._templates` 要预先塞进被 `get_template` 查的那几个真模板名**（否则 `if tt and tt.xxx` 分支全被跳过、
断言拿到 nil —— 又是假绿）。真 config 用 `package.path = "mods/local/?.lua;"` 直接 require 真文件，
**别桩**（要验的就是它和代码对不对得上）。

## E-quaterdecies. ⭐⭐ 动画键 / 帧名离线校验（2026-10-16 立，抓过一个真机才现形的 bug）

**为什么必须单独立一条**：引擎算动画键是
`s.prefix and (s.prefix .. "_" .. s.name) or s.name`（`all/systems/render.lua:398`），
查不到只 `log.error("animation %s not found", key)` 然后退化成 `EMPTY_LINK` ——
**不崩、不抛到插件侧，只在画面上变成"隐形"**。所以这类错只能靠实机盯画面，历史上真的漏过：
`kr6_powers` 的 l5b 子弹写了 KR6 的帧名 `Musketeers_TrailInstakill`（`prefix=nil`）
⇒ 键 = `Musketeers_TrailInstakill` ⇒ 库里没有 ⇒ 子弹隐形；而当时的探针只查"数值/帧名对不对"，
**完全没覆盖"这个键有没有被注册"**，全绿放行。

**工具**（`kr6_powers` 项目里已落地，别的插件照搬脚本即可）：
```bash
python .workbuddy/check_kr6_anim_keys.py     # 一键：刷基集 + 跑 lua 检查器
```
- `.workbuddy/_parse_anim_bin.py`：直接解析 `<game>/kr1/data/game_animations.bin` 得**本体全部动画键**
  （`u32 count` + 每条 `u16 len+name`、`u16 len+prefix`、`u32 count`；全小端）⇒ `_anim_keys_base.txt`。
  为什么不用 `animation_db:load()`：它走 `love.filesystem`，离线是桩，读不到 bin。
- `.workbuddy/check_kr6_anim_keys.lua`：真 `animation_db` + 真模板，逐模板算键并断言"已注册"。

**⚠⚠ 拿"真 animation_db"的正确姿势（比 A 节的"清缓存 require"更稳）**：
`love_stub.STUB_MODULES` 里有 `animation_db`，所以 `require` 拿到的是空壳。
本检查器**只需要插件自注册这一副作用**，不需要 bin ⇒ 用 `loadfile` 拿真模块、再把 `load` 打空：
```lua
package.preload['animation_db'] = nil
package.loaded['animation_db'] = nil
local A = loadfile('all/animation_db.lua')()
package.loaded['animation_db'] = A   -- 让插件内部 require('animation_db') 也拿到真身
A.load = function() end              -- 离线读不到 bin，别让它读
local keys = {}                      -- 包一层记录插件注册了哪些键
local orig = A.register_animations
A.register_animations = function(self, t) for k in pairs(t) do keys[k] = true end return orig(self, t) end
Spells.register_animations()   -- 装 HOOK
A.load(A)                      -- 触发 HOOK 里的自注册
```
⚠ `all/scripts.lua:8` 是模块级 `local A = require("animation_db")`，所以**必须在 require 插件之前**
就把 `package.loaded` 换成真身。`entity_db` 本身不依赖 `animation_db`，换掉不会伤 `E.Load()`。

**⚠⚠ 四个"间接"必须一起支持，否则全是假阳性**（第一版实测 4 条假 FAIL）：
1. `size_names` + **名替换**：`s.name = s.size_names[unit.size]`（`all/scripts.lua:1339`）⇒ 键 = `prefix_<size>`
2. `size_names` + **前缀加长**：`s.prefix = s.prefix .. "_" .. s.size_names[...]`（`all/scripts.lua:5866`、
   `kr1/game_scripts.lua:1208`）⇒ 键 = `prefix_<size>_name` ← 本体 `mod_stun` 就是这类（`stun_small_loop`/`stun_big_loop`）
3. `size_prefixes`（注意字段名是**复数**）：`s.prefix = s.size_prefixes[...]`（`kr1/game_scripts.lua:3336`）
4. **前缀留给运行时补**：模板静态 `prefix` 以 `_` 结尾（插件自写 `e.render.sprites[1].prefix = "kr6_re_lvl3_" .. i`）
   ⇒ 判定要放宽成"库里存在 `prefix..<非空>.."_"..name`"，并把**同族变体全部**标为已使用（否则假报未使用）

**⚠⚠ 两条引擎语义**：
- **复数 `attacks[].animations` 优先于单数 `.animation`**：`SU.y_soldier_do_loopable_ranged_attack`
  （`all/script_utils.lua:1478`）/ `..._loopable_melee_attack`（:2134）读的是复数数组；
  只有没有复数时才走单数（`SU.y_soldier_do_ranged_attack`:1604）。同时收两个 ⇒ 把"被覆盖掉的默认单数"
  当真需求 ⇒ 假 FAIL。
- **`attacks[].animation` 拿到的是「组名」不是「动画名」**：引擎交给
  `U.animation_name_facing_point` → `U.animation_name_for_angle`（`all/utils.lua:611`）——
  **`angles[组名]` 存在就用它的名单，不存在才把组名本身当动画名**。
  ⇒ 若 `sp.angles[nm]` 存在，nm 已被 angles 展开覆盖，不能再当字面名查。
  （`kr6_powers_mk_soldier` 的 `ranged.attacks[1].animation = "ranged_attack"` 配了
  `angles.ranged_attack = {"shoot","shootup","shootdown"}` ⇒ 真键是 shoot 系。）

**报告分桶**（避免噪声淹没信号）：
① 未注册 = **FAIL**（退出码 1）；② 注册了没人用 → 末段**不是**标准组名的单独列（疑似死键/错拼，
实测抓到 `kr6_mk_Bala_spin`），是标准组名（idle/walk/attack/death/in/out/…）的另列（脚本运行时按 group 取用，正常）；
③"靠运行时补前缀才命中"仅告知。⚠ 有噪声是正常的：脚本运行时赋的动画名静态看不到，
所以②只是**提示**，真正的门禁是①。

**⭐ 负向自测必做**：把已知正确的键临时改回错误写法跑一遍，确认 FAIL + 退出码 1 + 报出正确候选，
再还原（比对 md5）。不然你无法区分"检查器真的在工作"和"它什么都没查"（参见 E-octies 的假绿）。

## E-vicies. ⭐⭐ 探针直接驱动插件协程函数的四个坑（2026-10-19 乌鸦探针实证）

从插件源码**原文提取**某个 `M.xxx = function(this, store)` 到沙盒里驱动（不抄逻辑）时：

1. **提取块是赋值语句，不是函数**：`loadstring` 后必须先 `pcall(chunk)` 执行赋值、
   再取 `g.M.xxx` 当协程体；且沙盒要**预先建 `M = {}`**（`M.crow_update = f` 对 nil 索引直接崩，
   报错行号会落在赋值完成行=块尾，极具迷惑性），还要 `g._G = g`
   （块内 `rawget(_G, "E")` 才能拿到沙盒注入的 E）。
2. **提取边界用 `X = function` 匹配定义**：`find('M.mk_control_insert', 1, true)` 会命中
   **更早的引用**（`tt.main_script.insert = M.mk_control_insert`、注释）⇒ 提取出垃圾块，
   症状是"函数里 y_wait 找不到"。同理，函数体内含**多个行首 `end`**（`do..end` 包裹的 helper）
   时，终止边界必须取「下一个定义之前的最后一个 `\nend\n`」。
3. **引擎单例的桩签名按调用方式定**：插件里 `simulation:queue_remove_entity(this)` 是
   **冒号调用** ⇒ 桩必须 `function(self, e)`，`function(e)` 会把 **simulation 表自己**记进
   移除队列 ⇒ "removed==1" 假绿、断言实体字段时 `render` nil 崩。
4. **同帧多动画记录**：脚本常在同一帧 `animation_start("attack")` 后紧跟
   `animation_start("idle")` ⇒ 驱动器只看「最后一条动画记录」**永远**看不到 attack
   ⇒ 依赖 attack 时间戳的驱动条件恒假、探针假挂死。要扫「本帧新增记录区间」
   （记 `anim_seen`，resume 后遍历 `anim_seen+1 .. #records`）。

另：探针里 make_env 的局部（如 target_ref）在**外层驱动函数**里引用 = 全局 nil、条件恒假
—— E-octies 的现行犯变体，共享状态一律挂到 env 表上用 `env.xxx(store)` 取。

## F. 断言风格（照抄 verify_deadeye_arrow_tech.lua）

- `check(ok, label, detail)` 累加失败数，末尾 `os.exit(fails)`，`print('  PASS/FAIL ...')`。
- **每条结论都配一个"反例对照"**：例：自定义弹丸不被二次叠加，同时打印本体 `arrow_1` 二次 patch 后
  `reduce_armor=0.2 hooks=2` —— 既证明守卫有效，也证明"引擎本来就会叠"。
- 先打 FAIL 也不慌：常见原因是**时序**（见 D）和**断言写反**（比较对象取错了内外层）。

## G. 参考

- 项目内现成用例：`<项目>/.workbuddy/verify_deadeye_arrow_tech.lua`（43 断言，覆盖白名单/幂等/跨关/对照）
- 驱动真 `update` 协程的用例：`<项目>/.workbuddy/verify_deadeye_bounty_xp.lua`
  （端到端验证"技能施放 → 经验入账"，含上面 E-bis 的全部桩）
- 引擎语义探针：`<项目>/.workbuddy/probe_entity_load_semantics.lua`
- 官方 CI 示例：`KingdomRushDove/scripts/ci/check_text_expr.lua`、`scripts/ci/love_stub.lua`
- 相关技能：`kr-dove-plugin-config`（配置映射探针）、`iron-marines-hero-port`、`kr-dove-tower-port`
