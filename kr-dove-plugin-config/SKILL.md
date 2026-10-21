---
name: kr-dove-plugin-config
description: 给《王国保卫战 Dove 版》插件加"游戏内可改数值"的配置面板（plugins/<entry>/<entry>_config.lua），并把现有硬编码数值（如 balance.lua）改造成"默认值 + 配置覆盖"范式。含面板渲染硬约束、"强度项 / balance 固定值 / 模板写死"三档划分（哪些键该进面板、哪些硬编码、固定值必须放正确嵌套路径、殿堂点数顺序的坑）、on_config_change 热应用、require 缓存与原地 refill 的坑，以及逐键验证"配置是否真的落进数值表"的探针脚本。触发词：改 config、可游戏内修改数值、配置面板、balance 改配置、插件加配置、on_config_change、热重载配置、清理配置项、配置数值与默认值统一、硬编码、写死在模板里。
agent_created: true
---

# Dove 插件「游戏内可改数值」配置改造

已验证案例：`johnny_deadeye`（强尼·神枪手英雄插件，121 个数值 → 面板 **45 个强度键**；另 14 个布局固定值硬编码在 balance.lua（见 H 节）、8 个局部固定值写死在 hero_templates.lua（见 ③档 / C 段））。
同生态参考实现：`boss_crocs_hero`（config + reload_config + on_config_change）、`king_denas`（`require("<entry>.<entry>_config")` 直接吃）。

## A. 机制事实（读引擎源码确认，不是猜的）

文件位置由 entry 推导（`plugin/all/plugin_paths.lua:37-42, 65-75`）：

```
plugins/<entry>/config.lua              ← 元数据（entry/name/version/enabled/priority）
plugins/<entry>/<entry>.lua             ← 入口
plugins/<entry>/<entry>_config.lua      ← 玩家可调配置（就是这个文件）
```

- **`has_plugin_config` = `<entry>_config.lua` 是否存在**（`plugin_paths.has_plugin_config`，就是 `FS.getInfo`）。文件不存在 → 插件行没有「配置」按钮。
- 配置按钮：`dove_modules/gui/plugin_manager_components.lua:300-356`，路径 `plugin_paths.plugin_config_path(entry)`。
- **改完点「配置」里的保存只是"记忆待应用"，点插件管理器的「应用」才落盘**（延迟写盘，`plugin_manager_components.lua:330-345` + `plugin_manager_view.lua:3519-3531`）。
- 面板读配置：`storage:load_lua(config_path, true)`；写配置：`persistence.serialize_to_string` → 整个表被序列化回文件。
- 管理器**会自动往配置文件里补 `__default_config`**（`plugin_manager_view.lua:202-213, 248-259`）：它是"发布时的默认值快照"，用来在插件更新时判断"用户改过没有"。三个保留键不参与快照：`__default_config` / `key_label_map` / `key_order_list`。
- `require` 能拿到它：`plugin/plugin_main.lua:4-9` 把 `plugins/?.lua` 塞进 require path（`.`→`/` 由 require 完成），所以 `require("<entry>.<entry>_config")` 正好命中 `plugins/<entry>/<entry>_config.lua`。
- **插件管理器只在主菜单可达**（`all-desktop/screen_map.lua:1182` 是唯一 `PluginManagerView:new`）→ 不存在"关卡进行中改配置"的场景。
- ⭐ **技能价格只有两个旋钮**：`power.price_base` / `power.price_inc`。引擎取值 `all-desktop/game_gui.lua:8515`（同 `:9419`）：`price = power.level == 0 and price_base or price_inc` ⇒ **首次购买用 `price_base`、之后每次升级都用 `price_inc`**（不是"base + inc×级数"；`total = base + inc*(max_level-1)` 是 `:8064` 注释里的总价公式）。所以插件惯例是 `price_base = CFG.<x>_price_1`、`price_inc = CFG.<x>_price_2`。
  - ⚠ **不要凭空造 `*_price_3`**：模板从不读它（`sparking_geode_enhanced` 实证——AppData 玩家配置里有历史遗留的 `*_price_3` 死键，README 还照着写了，误导）。

## B. 面板硬约束（踩了就是"面板空白/少几行"，且不报错）

权威：`dove_modules/gui/editable_panel_view.lua`

1. **只渲染顶层标量**（boolean/number/string）与**全数字数组**（`_is_editable_type`，:365-383）。**嵌套表整片不渲染** → 配置必须是扁平结构，嵌套结构靠键名前缀展平（`shotgun_damage` / `skill_shotgun_damage`）。
   - ⚠ 同一函数里有个笔误：字符串数组会被判成不可编辑（`type(t)` 写成了循环变量 `t`，第三个别名恒为 "table" ≠ "string"）。所以别做字符串数组配置项。
2. **每行必须有 label**：`_render_list` 里 `if value ~= nil and label ~= nil`，任一为空就**静默跳过**（:424-430）。
3. `key_order_list` 存在时**只按它渲染、且不做过滤**（`_collect_sorted_keys`，:390-414）；没有它才按 label 排序。所以：
   - `key_order_list` 里的键必须在数据表里 + 必须有 label，否则该行消失；
   - 数据表里的键必须都在 `key_order_list` 里，否则永远看不见。
4. number 输入框走 `tonumber`（:212-229）→ **支持小数**，负号也行。
5. 数组渲染成"标题行 + 每项一行"。
   - ⚠ ⇒ **10 项数组 = 面板里 11 行长条**，而一项数值一行也放不下 10 个数。**成长类数值（生命/护甲/伤害/回复）不该做成数组配置项**，应做成**倍率标量**：基准数组留在 `balance.lua` 的 `DEFAULTS`，配置侧只给一个 `xxx_mult`（1 = 基准），`apply()` 用「基准 × 倍率」重算。面板因此每项只占一行。
   - 做法（`johnny_deadeye` / `boss_crocs_hero` 都用这套）：`scale_nums(key, base, round_int)`，**键名放第一个参数**（两条校验工具的正则都要求「键名紧跟左括号」）；生命/回复这类 UI 按整数显示的项取整，护甲/伤害保留小数。
     ```lua
     local function scale_nums(key, base, round_int)
         local m = cfg[key]
         if type(m) ~= "number" then return base end   -- 缺键/类型不对 → 原样用基准
         local out = {}
         for i = 1, #base do
             local v = base[i] * m
             out[i] = round_int and math.floor(v + 0.5) or v
         end
         return out
     end
     B.level_stats.hp_max = scale_nums("hp_max_mult", B.level_stats.hp_max, true)
     ```
   - ⚠ 换成倍率后，**对齐断言要跟着改**：不能再要求「DEFAULTS 值 == 配置值」（DEFAULTS 那时是基准数组），判据改为 `B == 基准 × 倍率`。而且抽取映射的正则要用 `[%w_]+`（**`%a` 不含下划线**，写成 `%a+` 会静默漏掉 `scale_nums` 这些带下划线的函数 → 倍率键全抓不到、数量对不上）。
   - 自检要覆盖「非 1 倍率真的在算」+「缺键回退基准」+「倍率 1 逐位等于基准」三条，否则倍率被静默忽略时不报错。注意复跑时必须**同时清 `balance` 与 config 两个模块的 `package.loaded` 缓存**，否则 `read_config()` 会走缓存拿到上一份配置（表现为倍率不生效）。
6. **布尔键可用**（开关型）。balance 侧配一个：

   ```lua
   local function bool(key, def)
       local v = cfg[key]
       if type(v) == "boolean" then return v end
       return def
   end
   B.xxx.enabled = bool("xxx_enabled", B.xxx.enabled)
   ```
   ⚠ 只认 `type(v)=="boolean"`：写成 `if v then` 会让字符串 `"false"` 变真。

## C. 改造范式：默认值 + 配置覆盖（原地刷新，不换表）

核心难点：数值表通常被多个模块 `require` 后长期持有引用（`hero_templates` / `hero_scripts` / 入口文件），**换表会让这些引用变陈旧**。所以刷新必须"原地 refill + overlay"。

```lua
local B = {}

-- 1) 纯默认值（唯一权威来源，别处不要再写死这些数）
local DEFAULTS = { max_speed = 2.5, level_stats = { hp_max = {...}, ... }, ... }

local function deep_copy(v) ... end

-- ⚠ 函数值不参与清除：否则会把 reload_config 自己一起清掉，
--   第二次调用就变 nil（B 上挂的接口要能跨多次 apply 存活）。
local function refill(dst, src)
	for k, val in pairs(dst) do
		if type(val) ~= "function" then dst[k] = nil end
	end
	for k, val in pairs(src) do dst[k] = deep_copy(val) end
end

local CONFIG_MODULE = "<entry>.<entry>_config"
local function read_config()
	local ok, cfg = pcall(require, CONFIG_MODULE)
	if ok and type(cfg) == "table" then return cfg end
	return nil
end

local function apply(cfg)
	refill(B, DEFAULTS)                 -- 先恢复纯默认值
	if type(cfg) ~= "table" then return end

	local function num(key, def)
		local v = cfg[key]
		if type(v) == "number" then return v end
		return def
	end
	-- 只接受「纯数字数组」且长度 >= min_len；返回副本，避免与配置表共享引用
	local function nums(key, def, min_len)
		local v = cfg[key]
		if type(v) ~= "table" or #v < min_len then return def end
		local out = {}
		for i = 1, #v do
			if type(v[i]) ~= "number" then return def end
			out[i] = v[i]
		end
		return out
	end

	B.max_speed = num("max_speed", B.max_speed)            -- 扁平 config 键 → 嵌套 B 字段
	B.level_stats.hp_max = nums("hp_max", B.level_stats.hp_max, 10)
	-- ... 逐项映射
end

apply(read_config())

--- 重新应用玩家配置（原地刷新，不换表）
function B.reload_config(new_config)
	package.loaded[CONFIG_MODULE] = nil    -- ⚠ 不清 require 缓存就永远读到旧值
	apply(type(new_config) == "table" and new_config or read_config())
	return B
end

return B
```

## D. 挂钩子（三处，缺一不可）

```lua
-- ① 每次关卡加载：重读配置（用户可能改了）+ 重建模板。必须在 require 模板模块之前。
function hook.E.load(load, self)
	load(self)
	local ok, bal = pcall(require, "<entry>.scripts.balance")
	if ok and bal and bal.reload_config then bal.reload_config() end
	package.loaded["<entry>.scripts.hero_templates"] = nil
	...再 require
end

-- ② 游戏内改配置：不实现这个函数，引擎会直接 restart.tmp() 重启整个游戏
--    （plugin_main.lua:200-233 can_hot_apply → plugin_manager_view.lua:3471-3477）
function hook:on_config_change(new_config)
	local ok, bal = pcall(require, "<entry>.scripts.balance")
	if not ok or not bal or not bal.reload_config then
		log.error("[<entry>] balance unavailable, config not applied")
		return
	end
	bal.reload_config(new_config)   -- 直接吃管理器传进来的新表，绕开磁盘/缓存时序
end
```

- 生命周期三接口是 `reload` / `unload` / `on_config_change`（`plugin/plugin_main.lua:127-135`），`init` 必需，其余可选；缺哪个就对该操作回退"保存并重启"。
- **数值烤进模板 → 改动只在下一张图生效**（实体是 `E:create_entity` 时对模板深拷贝）。因为管理器只在主菜单可达，所以"只重读数值、不重建模板"是可接受的；懒得重建就别硬重建（在菜单里 `E.entities` 可能还没建好，硬重建会报错）。
- 任何"读一次缓存成数字"的地方都要改成**缓存表、读值时取字段**（`bal.xp.gain_factor` 而不是 `local f = bal.xp.gain_factor`），否则热改不生效。

## D2. 三个实战坑（2026-10-16 给 kr6_powers 加面板时全部踩到）

### D2.1 `refill` 必须「原地填充」，不能整张换表

C 段示例里的 `refill(dst, src)` 是 `dst[k] = deep_copy(val)` —— **会换掉嵌套子表**。如果别的模块在**模块级**抓了子表引用（很常见）：

```lua
-- kr6_powers_spells.lua:199 / :355，位于文件顶层
local RE = B.reinforcements
local SO = B.aspect_of_sol
```

require 时就把引用抓死了。reload 后 `B.reinforcements` 换成新表 ⇒ `RE` 永久指向旧表 ⇒ **新数值对已注册的模板/脚本静默不生效**（无任何报错，最难查的一类）。

正确写法 —— **先收集旧引用、再清空、再原地回填**：

```lua
local function refill(dst, src)
	local old = {}
	for k in pairs(dst) do old[k] = dst[k]; dst[k] = nil end
	for k, val in pairs(src) do
		local prev = old[k]
		if type(val) == "function" then
			dst[k] = (type(prev) == "function") and prev or val   -- 保住接口函数
		elseif type(val) == "table" and type(prev) == "table" then
			refill(prev, val)          -- 原地填充，引用不变
			dst[k] = prev
		else
			dst[k] = deep_copy(val)
		end
	end
end
```

⚠ **顺序反了就白改**：先 `dst[k] = nil` 再去判断 `type(dst[k]) == "table"`，永远拿不到 `prev`。
⭐ **探针必须断言引用恒定**：`local ref = B.soldier; B.reload_config(cfg); ck('原地 refill', ref == B.soldier)`。

### D2.2 `reload_config` 与 `apply` 互相引用 ⇒ 必须前向声明

常见写法把 `function B.reload_config()` 放在 `apply(read_config())` **之后**。但 `apply` 末尾为了保住接口要把 `B.reload_config = reload_config` 重挂一遍 —— 此时 `reload_config` 尚未定义，**首轮挂上去的是 nil**，探针直接报 `attempt to call field 'reload_config' (a nil value)`。

正确序：

```lua
local reload_config                                     -- ① 前向声明（必须在 apply 之前）
local function apply(cfg) ... B.reload_config = reload_config end   -- ② apply 内重挂
reload_config = function(new_cfg) apply(new_cfg or read_config()) end  -- ③ 定义
apply(read_config())                                    -- ④ 首帧在定义之后才执行
return B
```

### D2.3 config 里别在表构造器内自引用

```lua
return {
    BTN_Y_FALLBACK = 118,
    BTN_Y = BTN_Y_FALLBACK,     -- ❌ nil！构造器里表达式的作用域只有「键名列表」
}
```
读不到同一构造器内声明的键 ⇒ `C.BTN_Y` 静默变 nil。**必须写字面值** `BTN_Y = 118`。

⚠ 另一条：**表构造器最后一个字段可以有尾逗号，赋值语句不行**。`C.a = 1,` 作为赋值尾逗号 → `unexpected symbol near '='`，且**报错行号偏移 1 行**（很容易误判到下一行）。

### D2.4 参考实现与「面板整页空白」的最快定位

- 范式样板 = `mods/local/johnny_deadeye/johnny_deadeye_config.lua`（**整个文件一个 `return { ... }` 表字面量**）+ `scripts/balance.lua` 的 DEFAULTS/refill/apply。同生态还有 `Alric_Overhaul_config.lua`、`boss_crocs_hero`。
- **面板打开整页空白** ⇒ 99% 是 config 没声明 `key_order_list` + `key_label_map`（B 段约束 2/3）。先用 grep 确认这两个键存在，再查值表与键序是否一一对应。
- ⭐ **面板权威代码不在 `mods/local` 下**，在 `KingdomRushDove/dove_modules/gui/editable_panel_view.lua`（+ `plugin_manager_view.lua` 管元数据/`__default_config`）。找面板渲染问题要先想到 `dove_modules`。
- **95 项这种量级别手写**：写个生成器从 `balance.lua` 的 `apply` 映射用正则抽 `num(cfg, "key", ...)` 键名，再用离线 lua 跑一遍取运行时默认值，最后生成「值表 + key_order_list + key_label_map」三段 —— **从构造上保证三者不可能失配**（kr6_powers 的 `.workbuddy/_gen_kr6_config.py` + `_emit_kr6_config.py` 可直接抄）。

## E. 验证探针（必做，否则"死旋钮"不会报错）

`verify_config_mapping.py`（本技能包同目录，用 lupa 跑真 Lua）：

```bash
python <skill>/verify_config_mapping.py <插件目录> --balance scripts/balance.lua
```

它做四件事：
1. **默认值抽查**：配置缺失时 B 必须是纯默认值（含 hash 键表如 `xp_level_steps`）。
2. **逐键哨兵映射**：一次只把一个配置键设成唯一哨兵值（数字键写 `700000+i`，布尔键写"原值取反"），reload 后与"无配置基线"逐字段 diff → 输出 `config键 → B.路径` 报告。**打印出来逐行看一遍**，确认落点没串位。
3. **死旋钮检测**：任何键改了 B 却毫无变化的，直接列出来（拼错键名、漏写映射都会被抓到）。
4. **reload 存活**：连续多次 `reload_config` 后 `B.reload_config` 仍是 function（抓 C 节那个 refill 清函数的坑）。

再补一条面板侧静态检查（同一脚本会跑）：`key_order_list` ↔ 数据键 ↔ `key_label_map` 三者必须一一对应，数组长度必须 ≥ balance 里 `nums` 的 `min_len`（**长度不够时是静默回退默认值，不报错**）。

环境准备（本机已具备，新机器上装）：
```bash
python -m pip install lupa --index-url https://pypi.org/simple
```

⚠ **中文路径**下 lupa 里 `dofile`/`io.open` 会报 `Illegal byte sequence`（Lua 的 C 层走 ANSI）→ 文件内容一律用 Python 读进来，再交给 Lua 的 `load(src, "@name.lua")()`。

## F. 同步与验收

1. 语法校验：`.workbuddy/lua_syntax_check.py <改动文件...>`。
2. ⚠ **别用 `diff -r` / `diff -rq`** —— 中文路径下会**漏报**（实测只报 1 项、实际 3 项）。用逐文件 MD5 工具 `.workbuddy/compare_plugin_sync.py <entry>`（默认只读报告；`--push <文件…>` / `--push-from-app` 才写，**绝不整目录覆盖**）。推前先把 AppData 侧备份到 `.workbuddy/backups/<entry>_<时间戳>/`。
3. **谁更新？先看 `config.lua` 的 `version`，再看内容**：AppData 是"装上去的那一版"，dev 是工作面 —— 用户常只改 dev。若 dev 的 `version` 更高（甚至只差一个小版本），**以 dev 为准往 AppData 推**；若两侧 version 相同而内容不同，才逐行看是谁在调参（AppData 的 `last_used_at` 被游戏回写是正常的，不算用户改动）。
   ⚠⚠ **游戏在跑的时候，推上去的 `version` / `enabled` 留不住**（2026-10-15 实测）：只要管理器保存一次，它就用**内存里的旧记录**把 AppData 一整批 `config.lua` 重写一遍 —— 刚推的新 `version` 被回退成旧值，`enabled` 被写成界面当前状态（那次它把除 `kr6_powers` 外的插件全写成 `enabled=false`，实为用户手动只留了在测的那个）。
   ⇒ ① 判断同步状态前先 `tasklist | grep -i love.exe` 确认游戏没在跑；
   ⇒ ② **绝不要为了"修版本号"去推 `config.lua`** —— 会把用户特意关掉的插件重新置成 `enabled=true`（覆盖他的启用状态），得不偿失；
   ⇒ ③ 别把"文件推过去了"当成"游戏会看到"：模板数值/插件列表都在启动时读一次，**改完一律要重启游戏**（G 节）。
4. ⚠ `<entry>_config.lua` 是**玩家可编辑文件**：管理器会在 AppData 版本里补 `__default_config` 并记录用户改过的值。**以后 dev→AppData 同步前必须 diff**，别盲目覆盖用户调过的数值；发布新默认值时保留 AppData 的 `__default_config` 语义（改了默认值的键，用户没自定义过就会被自动更新）。
   ⚠⚠ **别凭"AppData 文件更大 / mtime 更新"就断言玩家改过值**（2026-10-15 我踩过这个假阳性）：`__default_config` 是**发布时默认值的完整快照**（几十行）+ `key_label_map` 键序差异，单独就能让 AppData 那份比 dev 大 1KB 以上，而**所有键的值都和 dev 完全相同**。判据是 **diff 具体内容**：只有「dev 里存在的键值被改成别的数」才算玩家改过；只多出 `__default_config` / 键序不同 ⇒ 覆盖无损，可放心推。
5. ⚠ **用户手改数值时最常漏的是 `balance.DEFAULTS` 里"同族的兄弟键"**：一次只改了同批的一部分（例：把 revolver 的两个 xp 倍率改成 1.3，忘了 `shotgun` 那个仍是 1.5）。
   这类**不影响运行**（config 是覆盖层且键始终存在），但会违反「DEFAULTS 强度类与 config 1:1」的口径 → **改完数值一定跑一次对齐断言**，把 FAIL 逐条点给用户看（受 "其他的一概别碰" 约束时**只报告不擅自改**）。
   ⚠ **对齐断言的 SPOT 段常备两条以上"陈旧常量"**（历史上把 `revolver.max_range` 写 180、`horseride.speed_bonus` 写 0.6，实际早已是 190 / 0.8）→ 报 FAIL 时**先分清「真不一致」和「断言自己过期」**：判据是「config 的值 == DEFAULTS 的值」是否成立，成立就是断言过期（改为实际值），不成立才是真漏回填。
6. 版本号（`config.lua` 的 `version`）顺手 bump，管理器不依赖它 —— 但它是**上面第 3 条判"谁更新"的唯一可靠标记**，别省。
7. 验收：游戏内 → 插件管理器 → 该插件行应出现「配置」按钮 → 面板里逐项显示中文标签 → 改一个数点保存再点「应用」，**重启游戏**后进关验证生效（见 G 节：模板数值必须重启才会重新烤进模板，点「应用」不会）。
8. ⭐⭐ **README 复查清单（改完代码必跑；2026-10-10 `sparking_geode_enhanced` 实证：一次全量复查又抓出 4 处，且其中 2 处是"文档自己跟自己矛盾"）**：
   - ① **数值表**（等级/冷却/伤害/概率/范围）→ 对 `config` + `templates` 字面量 + 入口文件局部量 + **本体原值**（`kr1/*.lua`）。
   - ② **特效 / 音效归属**（最易张冠李戴）→ 对 `create_entity("<fx>")` / `S:queue("<sfx>")` 的**调用点**，别信"效果A"栏里写的名字。⚠ 同一个 README 的「功能特性」段和「版本日志」段可能一处对一处错。
   - ③ **文件结构树** → 直接 `ls` 对：文件可能被画进错误的目录、目录可能整个没列、`locales/` 这类**不被引擎加载的遗留目录**要注明。
   - ④ **配置项名 + 默认值** → 逐键对 `<entry>_config.lua`；历史遗留的死键（如在线文档写了 `*_price_3` 而 config 只有 `*_price_1/2`）要删。
   - 判据永远是**代码**，不是文档里另一处看起来"写对了"的地方。

## G. 已知边界

- 面板显示的是**静态配置值**，不是运行时有效值（运行时叠了等级/技能/临时 buff 的倍率不会反映到面板）。
- 描述文案（如英雄殿堂技能说明）是静态字符串，不会随配置改写 → 改了数值记得同步文案，或明确告诉用户"文案不跟着变"。
  ⭐⭐ **但更好的做法是「描述动态生成」**（2026-10-03 sorcerer_split_shot 定稿），从 `CFG` 现读数值拼串 ⇒ 改配置文案自动跟随，永不同步。落地要点：
  1. **同一份描述常有两处副本**，必须一起改：①技能菜单 `tower_menus_data.<tower>.tt_list`（`<entry>_menus.lua`）
     ②图鉴/i18n（`i18n.msgs[locale]["TOWER_XXX_DESCRIPTION_n"]`）。漏一处 ⇒ 两处显示不一致。
  2. ⚠⚠ **`%%d%%` 陷阱（静默、致命）**：想要「数字+百分号」必须写 **`%d%%`**。
     写成 `%%d%%` ⇒ `%%`→字面 `%`、`d` 是普通字符、`%%`→字面 `%` ⇒ **输出字面量 `%d%`，
     且该位置不消费任何参数** ⇒ 后面的实参**整体前移错位**：
     ```lua
     -- ❌ 显示「（%d%伤害）…基础伤害30-50，范围28」
     "…（%%d%%伤害）…基础伤害%d-%d，范围%d。"   -- 占位符4 但实参6
     -- ✅ 显示「（30%伤害）…基础伤害28-54，范围195」
     "…（%d%%伤害）…基础伤害%d-%d，范围%d。"
     ```
     Lua `string.format` **参数多于占位符不报错**（静默忽略）⇒ 只能靠校验抓。
  3. **校验法（离线、必做）**：数「有效占位符个数」是否 == 「实参个数」。
     `%%` 不算占位符；`%d`/`%s`/`%f` 算。可用 Python 复现 Lua 的 `%` 语义跑一遍，直接看渲染文本
     （模板：`re.findall(r'%%|%[ds]', fmt)`，`%%`→`%`，其余依次吃实参）。⚠ Python 原生 `%` 在参数多余时**会报错**，
     这反而能当"错位探测器"用。
  4. **不要硬编码「引擎侧的量」**：如术士变羊术 CD 别写 `22/20/18`，读引擎模板（见下条），fallback 写好。
  5. ⭐⭐ **文案键必须插件自带，绝不依赖本体键名**（2026-10-10 `sparking_geode_enhanced` 实证）。
     `_()` 查不到键就 **`return s`**（`all/i18n.lua:31-53`）⇒ 缺键 = 界面**直接显示键名**、零报错
     （"技能名称文本消失、只剩键名"就是这个）。而 **Dove 更新会改本体 i18n 键名**：
     四级塔 `TOWER_XXX_4_*` → `TOWER_XXX_LVL4_*`（`sparking_geode`／`dwarf`／`hermit_toad` 全中，2026-10 实证）
     ⇒ 靠本体提供的键**一夜之间集体悬空**。
     自查：`grep -rnoE '"(TOWER|HERO)_[A-Z0-9_]+_4_[A-Z0-9_]+"' mods/` 找插件里引用的本体键。
     ⚠ 渲染路径：技能菜单取 **`tt_list[power.level].tt_title/tt_desc`（按当前升级档）**
     （`all-desktop/game_gui.lua:9134-9165`，未满级时标题取**下一档**、描述走 diff），
     `tt_phrase` 则**无条件**渲染（`:9215`，每次开 tooltip 先 `hidden=true`）⇒ 每个 `tt_phrase`／`tt_list` 键都**必须**有值。
     ⚠ 插件目录下的 `locales/*.lua` **不被插件系统加载**（`plugin/*.lua` 里零引用）⇒ 那是**死文件**，
     真正生效的只有入口文件里 `override_strings()` 写的 `i18n.msgs[locale][...]`。
     💡 **旧构建快照可对照改名前后的键**：`%APPDATA%/LOVE/<identity>/.upgrade_tmp/_assets/kr1-desktop/strings/<locale>.lua`
     （本机实测该快照 2026-03-26 / CYCLE 0，仍是 `_4_` 命名）。
  6. ⭐⭐ **塔技能文案里的「每隔 X 秒」必须乘 `tcd`（2026-10-15 `leaf_vein_archer` 实证）**。
     运行时技能收口 `U.tower_ready_to_use_power` 是 `power_attack.cooldown * tw.cooldown_factor`，
     所以**技能 CD 天生随塔冷却系数缩放**；文案不跟着乘 ⇒ 局内吃到攻速加成（快速射击 0.9、
     高精灵祝福 `mod_high_elven` 等）后**实际缩了、面板数字不动/偏大**。用户报「技能不随加成缩小」
     且代码里确实乘了系数时，先查这里，别再翻代码。
     - 写法：`%$(冷却表达式) * tcd%$`（`tcd` = `ctx.ent.tower.cooldown_factor`，`utils.lua:2646`）。
       项目约定见 `docs/ai_tips/PROJECT_CONTEXT.md`「塔的每隔 X 秒一律乘 tcd」+ 例外清单
       （`timed_actions` / 士兵子单位 / `power_reinforcements_control` / 「加快 X 秒」类语义**不乘**）。
     - 渲染链路：`game_gui.lua:9133-9165`（技能面板）与 `screen_map.lua:6047-6074`（百科技能页）
       都传 `level` + `ent`，所以 `tcd` 有值、按当前升级档求值。本体范例：
       `_assets/kr1-desktop/strings/en.lua` 的 `TOWER_ARCANE_BURST_DESCRIPTION_1`。
     - ⚠⚠ **`%%$` 与 `%$` 的差别取决于"它在哪"**：表达式**当 `string.format` 的参数**（`%s` 传入）时
       写**单个 `%$`** —— 参数不做转义，写 `%%$` 会原样输出，`format_text_expr` 解析出残缺表达式
       ⇒ 求值失败 ⇒ **整段渲染成「每隔%秒」**（`eval_text_expr` 是 pcall，静默返回 nil ⇒ 空串，不报错）。
       只有把表达式**拼进格式串字面量里**时才需要 `%%$`。与上面第 2 条的 `%d%%` 是同一类坑的镜像。
     - 冷却表达式**直接读模板字段**（`T('tower_x').attacks.list[n].cooldown`），这样配置热更新
       （`write_values`）改值后文案也跟着走，不必再手工同步。
     - 索引要兜底：按等级取的数组（`per_level_cooldown`）写成 `[max(1, level)]`
       —— `level` 在 `ctx.level` 缺省时是 **0**（`utils.lua:2639`），`[0]` = nil ⇒ 同样静默变空串。
  7. ⭐ **文案不是"动态生成"也能吃到 `tcd` —— 静态 `string.format` 照样行**（2026-10-15 三处实证：
     `Shining_Holy_Nuclear_Tower/assets/strings/zh-Hans.lua`、`sorcerer_split_shot`（主文件 + `_menus.lua`
     **两份副本都要改**）、`alien_bug_nest_mod/ui/i18n.lua`）。做法：把原来那个 `%d` / `%.0f` 占位改成
     `%s`，表达式**当参数**传：`string.format("每隔%s秒…", CD_EXPR, …)`。
     - ⚠⚠ **`string.format` 的格式串里绝不能出现裸 `%$`** —— Lua 会直接抛 `invalid option '%$'`
       （`%` 后必须跟格式符）。所以表达式**不能**直接拼进格式串，必须走 `%s` 参数；
       若确要拼进格式串，得写 `%%$`（那样 `format()` 才输出 `%$`）。**参数写法不易错，优先用它。**
     - 静态文案没被提前求值：`_()` 是**纯查表**（`all/i18n.lua:36-57`，不做表达式求值）
       ⇒ `tt_desc = _("KEY")` 拿到的仍是带 `%$…%$` 的原始串，渲染期才求值，**这一点是安全的**。
     - 索引校对：`game_gui.lua:9133-9176` 的 `upgrade_power` 分支按 `tt_list[current_level]` 取，
       **索引 N ⟺ `level = N`**，所以三档文案各按自己的等级求值；`screen_map.lua:6047-6074` 同。
     - ⭐⭐ **数值源：优先引用模板字段；冷却只存在于插件 cfg 时，给模板加「插件自有键」，别用本体键名**
       （2026-10-16 `Demon_Sentinel` 实证）。表达式环境只注入 `T/E/level/tcd/grow/…`，**没有 `cfg`**
       ⇒ 想用配置里的冷却数组，必须让模板先暴露它。
       ⚠ **不要用本体的 `powers.<x>.cooldown`**：本体该键的语义是**运行期标量**
       （`U.tower_ready_to_use_power(power, power_attack, …)` 读 `power_attack.cooldown`，
       而 `kr1/tower_scripts.lua` 里有不少调用把 **power 对象自己**当 `power_attack` 传），
       同时 `upgrades.lua` 又对个别塔 `mul_arr(powers.<x>.cooldown, cd)` 按数组乘 ⇒ **两种形态混用**，
       用本体键名有被本体补丁改写/塌形的风险。改用自有键名（沿用 `leaf_vein_archer` 已建的 **`per_level_cooldown`**）：
       `tt.powers.skillN.per_level_cooldown = cfg.skillN_cooldown`，
       表达式写成 `%$T('tower_x').powers.skillN.per_level_cooldown[max(1, level)] * tcd%$`。
       ⭐ 反过来：**已有本体字段就别另造**（`attacks.list[n].cooldown`、`powers.polymorph.cooldown_base`
       直接引用，天然同步、还省一次改动）。
     - ⭐ **纯 `..` 拼接的描述串不需要 `%s` 中转** —— 只有走 `string.format` 的才要把占位符改 `%s` 再当参数传；
       拼接场景**直接内联单个 `%$…%$`** 即可（`Demon_Sentinel` 就是这么改的，最省事）。
     - ⭐ **百科页传的也是真实体**：`screen_map.lua:5838` `local dt = E:create_entity(tower_name)`
       ⇒ `dt.tower.cooldown_factor` 存在（值 1）⇒ 局内面板与百科页都用**裸 `tcd`** 即可，
       不需要 `(tcd or 1)` 兜底；但两处都要验（百科应显示基础值）。
     - 探针套路可复用：`.workbuddy/probe_cd_tcd_3spots.lua` / `.workbuddy/probe_demon_sentinel_cd_desc.lua`
       （引擎 `RT` 建同名占位模板、只给表达式需要的字段 + 从插件文件文本 `match` 抓表达式常量防漂移 +
       逐档 × factor 断言输出 + 「老写法已消失 / 新写法出现 N 次」的计数断言）。
     - ⚠ **改运行时 CD 时务必连带扫文案**：一批插件只改运行时、不改文案 ⇒ 面板数字不动。
       排查口径：`grep -n "冷却\|每隔\|间隔" <插件>/*.lua | grep "DESCRIPTION\|tt_desc"`。
- ⭐ **术士塔变羊术 CD 真值 = 20/18/16 秒**（1/2/3 级）（**2026-10-15 修正**）：
  `kr1/mage_towers.lua:177-178` `powers.polymorph.cooldown_base = 22` / `cooldown_inc = -2`；
  **运行时公式 = `cooldown_base + cooldown_inc * pow.level`，`pow.level` 取 1/2/3（不是"从 0 起"）** ——
  `kr1/tower_scripts.lua:2902` 与 sorcerer 插件 `_scripts.lua:761` 都是这一行 ⇒ 20/18/16。
  本体自己的文案就是这个口径：`_assets/kr1-desktop/strings/zh-Hans.lua:156`
  `TOWER_SORCERER_POLYMORPH_DESCRIPTION_1 = "每隔%$(T('tower_sorcerer').powers.polymorph.cooldown_base
  + T('tower_sorcerer').powers.polymorph.cooldown_inc * level) * tcd%$秒，…"`。
  ⚠⚠ **历史踩坑**：曾按「level 从 0 起」写成 `base + inc * (level - 1)` ⇒ 文案显示 22/20/18，
  比真实值**整高一级**；sorcerer README v2.0.1 还把它记成"对齐引擎真实值"（连带把 README 数值表也写错了）。
  **移植/复刻时照抄本体那行表达式即可，别自己推 level 基准。**
  插件里若要取数值：`E:get_template("tower_sorcerer").powers.polymorph`（fallback `22 / -2`）。
  时机可行：`<entry>_menus.lua` 在主文件 `hook.E.load` 里、**模板注册之后**才 require
  （sorcerer 主文件 `:515 modify_sorcerer_tower()` → `:519 require menus`）⇒ 读得到模板。
- ⭐⭐⭐⭐ **改配置要「当场生效」，必须同时做三件事**（2026-10-20 实测定论，纠正旧结论）：
  1. **`E.load`（小写）与 `E.Load`（大写）是两个不同函数**：小写只在**首次**加载本体模板；
     大写是**每次进关**的入口，内部 `table.clear(self.entities)` → 从 `entities_backup` 深拷贝重建
     （`all/entity_db.lua:26-43`，其注释明确写"插件应当 HOOK 该函数"）。
     ⇒ **只挂小写 = 面板改好的模板在「点开始游戏」那一刻被旧快照覆盖**，
     症状是「PROBE/离线都对，进关放技能还是旧值，只有重启才生效」。必须 `HOOK(E, "Load", ...)`。
  2. **注册完把新模板写回 `E.entities_backup`**（引用同步即可），否则下一次进关又被旧快照盖掉。
  3. **消费点实时读 balance**：冷却这类每次读 B 的天然即时；模板字段（伤害/护甲/时长）最好在
     创建实体时再从 B 写一遍，双保险。
  · 已在场实体永远保持旧值（`create_entity` 是 quickcopy）⇒ 改完必须重新召唤/建造。
  · ⚠ 排查铁证组合（**正式版已按用户要求删掉这些落盘日志**，复现时临时加回，别长期留）：
    `[boot]`（版本标记）+ `[apply] save keys=[...]`（写盘键）+ `B: ...`（balance 实际值）
    + `PROBE`（apply 后真建实体读字段）+ `[spawn]`（游戏内实际创建）。**PROBE 是新值而 spawn 是旧值
    ⇒ 一定是 entities 被重建过**，直接查 `E.Load` 钩子。
    ⚠ 加/删日志都别碰 `M._seg` 进度标记：探针 `verify_kr6_live_inject` 断言它（删了假红）。
  · ⚠ 点「开始游戏」瞬间会调 `settings.boot → register_templates`，此时本体 base 模板还没加载，
    `E:register_t(name, base)` 里 `quickcopy(nil)` 会抛 `all/entity_db.lua:11 bad argument #1 to 'pairs'`
    ⇒ **整套模板一个都不注册**。注册前必须做 base 存在性预检，缺就安静 `return false`。
- 布尔键：`_is_editable_type` 接受 boolean，balance 侧写个 `bool(key, def)`（`type(v)=="boolean"` 才采用）即可。
  ⚠ `verify_config_mapping.py` 的哨兵对布尔键会写 `not 原值`，并同时收集布尔字段——否则会把布尔键全报成"死旋钮"（假阳性）。
- ⭐⭐ **`GGLabel` 是单行控件，塞多行必崩**（自定义面板/提示文案都适用）：
  `all/gg_views.lua` 的 `_draw_self` 用 `fit_lines = 1` 做自动缩放，**含 `\n` 或超宽时字号会被一路降到 <1 仍不合，
  `self.font` 留在 nil ⇒ `G.setFont(nil)` 崩**。⚠ 中文 locale 下 `fit_lines > 1` 的**多行分支根本不生效** ⇒
  **多行提示必须拆成多条 label**（每条一行），别指望一个 label 里换行。
- ⭐⭐ **kui 关闭弹窗禁用 `destroy()`**：`KView:destroy` 会把 `colors` 等字段**全部置 nil**，
  而 `kui.update`（`klove/kui.lua:1469-1476`）用 `_last_enter_view` 记住悬停对象、**下一帧**仍会对它调 `on_exit`
  ⇒ 崩。**关闭 = `hidden = true` + `parent:remove_child(...)`**；`destroy` 只用于整棵 UI 树消失。
  稳妥起见 `on_enter` / `on_exit` 里加 `if self.colors then` 防护。
- ⭐⭐ **配置面板"按英雄前缀取键"极危险**（多英雄共用一个面板模块时）：①卡片上的 `prefix`
  **未必等于**真实配置键前缀（阿什比特卡片写 `prefix="dragon_"`，但键是 `ashbite_*`）；
  ②前缀之间有**包含关系**（`dragon_` 会吞掉 `dragon_arb_` / `dragon_bone_` / `dragon_gem_` / `dragon_sun_`）
  ⇒ 任何"按前缀批量取键/改值/渲染"**必须优先用 `key_group_map[hero_key]` 的显式键列表**，前缀只当兜底。

## H. 该不该进面板：强度项 vs 固定值（三档模型）

已验证：`johnny_deadeye`（2026-09-30 落地两批：config 从 8263 → 7189 字符剔掉 14 个非强度键，再 → 6816 字符剔掉 7 个"写死进模板"的键）。

**判据只有一条**：*"玩家调这个数值，是在调英雄的强弱，还是在改开发期的排版？"*

| 档 | 内容 | 去处 |
|---|---|---|
| ①**强度项** | hp/护甲/伤害/冷却/射程/技能倍率/移速加成/xp 倍率… | **留在配置面板**（`<entry>_config.lua` 三表 + `balance.apply()` 的 `num()/nums()/bool()`） |
| ②**共享固定值** | 位置偏移 / 贴图与特效**缩放** / **UI 间距** / **动画帧数** / `dead_lifetime` 之类（**多个模板/脚本都要用**） | **移出面板**，硬编码进 `balance.lua` 的「固定值」区（仍走 `B` 表读取，只是**不被 `num()` 覆盖**、也不进 config 三表） |
| ③**局部固定值** | 只在**一处**用的常量（弹速 / 连发数 / 弹夹容量 / 殿堂面板点数…） | **移出面板**，直接写死在用它的文件里（`scripts/hero_templates.lua`），**连 B 表都不走**，`balance.lua` 里**不再定义** |

理由：面板是给玩家看的，塞进"受击点 Y 偏移 25""爆炸印记缩放 1.0"只会让人一脸懵；而这类常量开发者改一处就该全局生效，不该被玩家存档里的旧值覆盖。**②与③的取舍**：只有一处消费 → 直接写死（少一层间接，改起来就在眼前）；多处消费 → 放 ② 走 `B` 表，避免同一个数抄两遍。

⚠ 用户口径：**"写死在 templates 里"≠ 放 ②**。② 走 `B` 表、③ 不走 —— 用户点名"移动到 templates 里写死"时按 ③ 处理（把 `B.xxx` 换成字面量、`balance.DEFAULTS` 里删掉定义），别只做 ②。

### 清理清单（每删一个键，四处都要动，漏一处就出问题）

1. **值表** 删该行（`^\t<key>\s*=[^\n]*\n`）。
2. **`key_order_list`** 删该项 —— ⚠ **一行常挤多项**（`"a", "b",`），**不能按整行删**，要按 `'<key>",[ \t]*'` 删单项，删完再单独清被掏空的整行（`re.sub(r"^\t+[ \t]*\n", "", ...)`）。
3. **`key_label_map`** 删该行（`^\t\t<key>\s*=\s*"[^"]*",\n`）。
4. **`balance.apply()`** 删对应那一行覆盖 —— 这一步才是"真硬编码"：不删映射，`DEFAULTS` 里留着定义也没用，玩家旧配置里若还残留该键会继续被覆盖。
   ③ 档还要多做一步：**删掉 `DEFAULTS` 里的定义**（③ 不走 B 表，留着就是死代码），并把消费点的 `B.xxx` 换成字面量。

**每处删前先断言出现恰好 1 次**，末尾再自检残留（`grep` 该键 0 命中）。写成一个定向脚本（本项目 `.workbuddy/patch_deadeye_config_trim.py` / `patch_deadeye_config_trim2.py`），比手改安全 —— 尤其是 `<entry>_config.lua` 可能正被游戏/用户实时改写（Edit 工具的"读后未变更"校验会一直失败）。

### ⚠⚠ 删键时最容易漏的**第 5-7 处**：下游注入行 / 消费点 / 文档

上面「四处」只保证**面板与 balance 一致**。若被删的键是**技能数组**（`skills.xxx.*`）
或被模板/脚本文本引用的字段，还要清：

5. **模板注入行**（`hero_templates.lua`）：`tt.hero.skills.crack.xxx = B.skills.crack.xxx`
   —— 删了 balance 的键后这行变成 `= nil`，**不报错**，但技能表少一个字段；
   下游 `level_up` 里 `s.xxx[sl]` 就会 `attempt to index a nil value`（**崩在别处，难定位**）。
6. **文案生成器**（`hero_room_texts.lua`）：`top(cr.extra_armor, ...)` 之类的引用
   —— 键没了会静默走 fallback 值，**殿堂显示的字面量与实际不符**（假绿）。
7. **`README.md`** 的数值表 / 配置面板项数表（**项数会变，必须同步**）。

> 📌 判断"要不要管第 5-7 处"：`grep -rn '<key>' <plugin>/` **全目录**，
> 命中除 config/balance 之外的任何文件都要逐一确认。
> 本次 ember 实战：删 3 个键 ⇒ 连带改了 6 个文件
> （`hero_scripts.lua` 的 level_up 写入段 + aura.update 消费段 + README + 文案）。

### ⚠⚠ **新增**键是对称的，而且总是漏「校验脚本的期望值」

新增一个配置键要动的地方（与删键镜像，同样四处 + 下游）：
1. `config`：值本身；2. `key_order_list`；3. `key_label_map`；
4. `balance.DEFAULTS` 同路径的默认值 + `apply()` 里加 `num("key_name", ...)` / `nums(...)`；
5. 下游真实消费点（模板注入行 / 脚本读取 / 文案引用）。

> ⭐⭐ **第 5 处（模板注入行）是「静默失效」的重灾区，务必单独确认**：
> `hero_skill` 组件的自定义字段必须显式注入模板 —— `all/components.lua:480` 的注册字段
> （name/level/xp_gain_factor/xp_gain/xp_level_steps/hr_*）里**没有你新加的键**。
> 漏了这行 ⇒ 运行期 `this.hero.skills.<x>.<新键>` **就是 `nil`** ⇒ 功能**完全不生效且零报错**。
> 实例（2026-10-01 ember 业火回血）：config 改了、`balance.DEFAULTS` 改了、`apply()` 读了，
> 唯独漏了 `tt.hero.skills.hellfire.heal_ratio = B.skills.hellfire.heal_ratio`
> ⇒ 触发业火**永远不回血**，控制台干干净净。
> ⇒ **必须配一条探针断言模板已挂该键**：
> `check(E:get_template('hero_xxx').hero.skills.<x>.<新键> ~= nil, ...)`
> （离线跑真模板即可，无需进游戏）。
>
> ⭐⭐ **「注入了」≠「生效」：字段名必须与引擎实际读取的键名一致**（2026-10-04 `hero_zezitra` 实证）。
> `hero_skill` 组件里**只有** `name` / `level` / `xp_gain_factor` / `xp_gain` / `xp_level_steps` / `hr_*`
> 是引擎认的（`all/components.lua:480-486`）；其余自定义键（如 `pets_max`）**只靠脚本自己读**。
> 实例：KR1 原版把技能经验数组写在 `hero.skills.wormtongue.xp_from_skill = {100,200,300}` ——
> 这个键 **Dove 的组件没注册、全引擎也没人读**，而 `SU.hero_gain_xp_from_skill`
> （`all/script_utils.lua:1001`）读的是 **`skill.xp_gain`**（读不到就退化成 `技能等级 × xp_gain_factor`）
> ⇒ **面板旋钮是死的**，实际每次只给 1/2/3（对照：同英雄 `double_shadow` 写的是正确的 `xp_gain` ⇒ 生效）。
> **通用检查**：新增/移植任何技能字段前，先 `grep` 引擎**谁读这个键名**；读不到就不是"注入成功"。
> 修法是把数组挂到引擎真读的键上（`xp_gain`），并用**真跑入账函数**的探针断言钉死
> （例：`SU.hero_gain_xp_from_skill(fake, skill)` 后 `fake.hero.xp_queued == skill.xp_gain[level]`，
> 而不是只断言"模板上有这个字段"）。

> ⭐⭐ **逆操作「削减技能等级」同样要成套联动（四处），只改 `max_level` 必留脏引用**（2026-10-03 Demon_Sentinel 实证）：
> 1. `config` 里该技能的 `<skill>_max_level`；
> 2. `balance` 里对应的**数值数组**（把多余等级的元素**砍掉**，别只留 max_level 变小）；
> 3. **i18n 的 N 级文案**（`TOWER_XXX_DESCRIPTION_<n>` / 技能说明逐级串，删掉多余等级那条）；
> 4. **模板侧 `tower_menus_data.<tower>.tt_list` 的 N 级条目**（写死的 `I` / `II` / `III`）。
> ⚠ 只把 `max_level` 调小 ⇒ `tt_list` 仍引用已被删掉的键 ⇒ **脏数据 / 文案缺失**（不报错）。
> ⇒ 砍等级 = 把上面四处**一起**按等级截断。

> ⭐⭐ **第 6 处 —— 校验脚本里写死的期望值**，是**最常漏、也最坑**的一处：
> - `check_config_ember.py` 的 `checks = [(key, [期望数组]), ...]`；
> - `verify_*_templates.lua` 里对**数值 + 单位注释**的断言（如 `'…duration = 技能3级（8 秒）'` 这种把值写进
>   提示串的，值改了注释就是错的，虽然断言本身从 `B` 动态读会 PASS）。
>
> **漏了会怎样**：改完数值全部校验"全绿"，其实校验器还拿着**上一版期望值** ⇒ 假绿；
> 或反过来报**假 FAIL**（本次 ember 改 `duration` 4/6/8→4/5/6，`check_config_ember.py` 立刻 FAIL）。
> ⇒ **每次改数值，第一件事就是全目录 grep 旧值**，把探针/校验脚本一起改掉，再跑校验。
>
> ⭐⭐ **根治手法：期望值优先「从被测对象动态取」，别写死字面量。**
> 例：断言模板写回正确，写 `h.hero.level_stats.armor[10] == B.level_stats.armor[10]`
> （而不是 `== 0.2`）—— 以后用户再调平衡，这条**永不假红**。
> 只有"这个值本身就是契约"（如用户指定的 `heal_ratio = 0.10`）才写死。
> ⚠ 另注：**标量**字段别塞进只配 `{}` 的数组正则（`arr(key)` 会返回 `None` ⇒ 假 FAIL）。
>
> ⚠⚠ **假红时先别改代码**：用户改平衡后，脚本里写死的期望会 FAIL，那是**脚本过期**不是代码坏。
> 顺序永远是：**查代码实际值 → 看注释里用户是否标注过调整 → 问用户取哪口径 → 再决定改哪边**。
> 一键核对：`grep -rn '<旧数值>' .workbuddy/check_*_<plugin>*.py .workbuddy/verify_*<plugin>*.lua`。

### ⚠⚠ 「三处同步」必须靠**机械校验**，人手改必漏且零报错

新增/删除一个配置键要同步 **`config` 值 / `key_order_list` / `key_label_map`** 三处。
第 2、3 处**漏了完全不报错**，但后果不同：
- 漏 `key_order_list` ⇒ 面板顺序错 / 该项不显示；
- 漏 `key_label_map` ⇒ **面板里根本看不到这一项**（面板只渲染 `key_label_map` 有键的），
  玩家"这个配置怎么没了"，而代码/探针全绿。

⭐ **实测（2026-10-01 ember 业火回血）**：已加好的 `skill_hellfire_heal_ratio` label 行
在收尾时**静默消失**（文件被游戏/linter 反复回写，`Edit` 多次报 "modified since read"）
⇒ 只有同步脚本报 DIFF 才暴露。**是动态对拍抓到的，不是我肉眼看出来的。**

⇒ 校验脚本必须**动态对拍三张表**（不写死项数）：
```python
print("[A] order 里缺 label:", set(order) - set(labels))     # 必须为空
print("[B] label 里缺 order:", set(labels) - set(order))     # 必须为空
print("[C] order 里 config 顶层没有:", set(order) - set(real_top))
print("[C2] config 顶层没进 order:", set(real_top) - set(order))
```
并打印 `config 顶层键 / order / label` **三个计数**，一眼看出是否齐（本次修好后 = `44 / 44 / 44`）。
⇒ **改完 config 一定要跑这个脚本**，别信"我记得加了"。

### ⚠⚠ 「数组 → 标量」的语义变更要三件一起动（2026-10-04 `hero_zezitra` CD 实证）

把某个"按技能等级分档的数组"改成"固定标量"（例：CD `{26,24,22}` → `25`）时，容易只改一半：
1. **`apply()` 换函数**：数组用 `nums(...)`、标量必须换 `num(...)`（写反 ⇒ 值类型错/静默回落）；
2. **读取方别再索引**：原来 `B.x.y[level]` 的调用点要改成 `B.x.y`（或干脆抽个 helper，
   本插件是 `cooldown_for(hp_max)`）；
3. **给旧配置残留兜底**：用户本地 config 可能还留着旧数组 ⇒ 读的时候写
   `tonumber(v) or <默认>`（`tonumber(table)` 返回 nil ⇒ 自动回落，不会崩）。
⭐ 顺带：**面板"少一行"是静默的** —— 只改了 `key_order_list` / `key_label_map` 而漏了**值表那一行**，
该行就永远不渲染、也不报错（本插件这次真踩了，靠探针"值+order+label 三者齐不齐"的断言抓到）。
⇒ 任何 config 改动都要跑那条断言，别靠肉眼。

### ⚠⚠ 最大的坑：②档固定值必须放回**正确的嵌套路径**，不能当 `DEFAULTS` 顶层平键

下游读的几乎都是**嵌套路径**，不是平键：

```lua
-- 反例：把固定值放成 DEFAULTS 顶层平键 → 下游全变 nil（贴图/动画错位，且不报错）
DEFAULTS = { horseride_hit_offset_y = 25, ammo_bullet_size = 6, ... }

-- 正例：放回所属表内（下游 B.horseride.hit_offset_y / B.ammo.bullet_size 才读得到）
DEFAULTS = {
    horseride = { ..., hit_offset_y = 25, -- [固定] 受击点 Y 偏移
                       mod_offset_y = 25, -- [固定] 状态图标 Y 偏移 },
    ammo      = { ..., bullet_size = 6,   -- [固定] UI 弹头图间距（px）
                       offset_y   = -10,  -- [固定] 整排 Y 偏移 },
    revolver  = { ..., shoot_times = 6,   -- [固定] 每两发间隔（帧）
                       shoot_time  = 3 }, -- [固定] 出枪耗时（帧）
}
```

- 判定"下游读的什么路径"：`grep -n "horseride\." scripts/*.lua` 看消费点写的是 `B.horseride.hit_offset_y` 还是 `B.horseride_hit_offset_y`。**几乎所有"分组短语"式的固定值都该挂在某个子表下**（`horseride.` / `ammo.` / `bullseye.` / `revolver.` / `shotgun.` / `wanted.`），只有真正的全局量（`sprite_scale` / `marker_scale` / `dead_lifetime`）才在顶层。
- **动画帧数直接内联进所属表**（`revolver = { shoot_times = 6, shoot_time = 3 }`），不要写成表外赋值 `DEFAULTS.revolver.shoot_times = 6` —— 后者会让按 `^\t<key>\s*=` 扫默认值键的静态探针**漏判**（它在 `local DEFAULTS = {` 到 `\n}\n` 的区块里找不到）。
- **这个坑靠探针兜底**：本项目 `.workbuddy/probe_deadeye_config.py` 的 **B 段**专门校验"14 个固定值是否真的硬编码到位"，三项判定 = ① 在 `DEFAULTS`（**按嵌套路径逐段下钻** 判定，不是找顶层平键）② 不在 config ③ 不被 `num()` 覆盖。初版把三个字段误放顶层时，它一次报出 6 个 `DEFAULTS=False ... FAIL`（`horseride_hit_offset_y` / `ammo_bullet_size` / `bullseye_explosion_fx_scale` / `revolver_shoot_times` …）→ 直接定位。

```python
# 探针 B 段的嵌套路径判定：扁平 config 键名 → balance 真实路径
HARDCODED = {"horseride_hit_offset_y": "horseride.hit_offset_y",
             "ammo_bullet_size":       "ammo.bullet_size", ...}

def in_defaults(path):
    parts = path.split(".")
    seg = dblock                                   # `local DEFAULTS = {` 到行首 `}` 的区块
    for i, p in enumerate(parts):
        if i < len(parts) - 1:                     # 中间段：下钻进子表
            m = re.search(r"^\s*" + re.escape(p) + r"\s*=\s*\{", seg, re.M)
            if not m: return False
            seg = seg[m.end():]
        else:                                      # 末段：必须是 `key =` 定义
            return re.search(r"^\s*" + re.escape(p) + r"\s*=", seg, re.M) is not None
```

### 数值口径与回归

- **`<entry>_config.lua` 的当前值 = 权威**，`balance.DEFAULTS` 的强度项与之 1:1 对齐（"统一为 config 里的"）。改数值先改 config，再让 balance 跟随。
- 对齐要有**离线断言**兜底（本项目 `.workbuddy/verify_deadeye_balance_alignment.lua`，当前 **45 项** —— ⚠ 此数随配置增删变化，删键后必须同步，别当成常量）：做法是 ① `package.preload['<entry>.<entry>_config'] = function() return nil end` → 抓**纯默认值快照**；② 清 `package.loaded` 重来 → DEFAULTS + 配置覆盖；③ 从 `balance.lua` 源码用 `B%.([%w_%.]+)%s*=%s*%a+%(%s*"([%w_]+)"')` 抽「B 路径 ⇄ config 键」映射；④ 断言 DEFAULTS 值 == 配置值、覆盖后 B 值 == 配置值。
  - 踩坑：捕获组一定要 `B%.(` + `)`，别把前导 `B.` 也吞进去，否则 `resolve(DEFAULTS, "B.fixed_stats.health")` 会去找不存在的 `B` 键 → 全报 `nil`。
  - 每删一批键，记得同步这个脚本的「条目数阈值」与抽查表（删掉已硬编码的键，别留着 `fixed_stats.*` 之类不存在路径）。

### ③档（写死进 templates）的探针：C 段 + C2 段

同一个 `probe_deadeye_config.py` 再加两段（本项目已落地）：

- **C 段**：每个写死的键 → 四项判定「不在 config / 不被 `num()` 覆盖 / 字面量确实出现在目标文件 / 旧 `B.xxx` 引用已从所有脚本消失」。用「**字面量正则 + 旧引用负向**」两个方向同时卡，比只看一边稳。
  ```python
  TEMPLATE_HARDCODED = {
      # config 键 -> (字面量应出现的正则, 必须消失的旧 B 引用)
      "revolver_bullet_speed": (r"min_speed = FPS \* 20 -- \[固定\] 左轮弹速", "B.revolver.bullet_speed"),
      "shotgun_bullet_speed":  (r"min_speed = FPS \* 20 -- \[固定\] 霰弹弹速", "B.shotgun.bullet_speed"),
      "stat_attack":           (r"tt\.hero\.fixed_stat_attack = 7\b", "B.fixed_stats"),
  }
  ```
  ⚠⚠ **正则必须窄到「只有目标那一处能匹配」**（2026-10-04 踩）：johnny_deadeye 的左轮与霰弹弹速代码**一字不差**
  （都是 `tt.bullet.min_speed = FPS * 20`），唯一区别是行尾 `-- [固定] 左轮弹速` / `-- [固定] 霰弹弹速`。
  若沿用宽松正则 `tt\.bullet\.min_speed = FPS \* 20\b`，**删掉其中一条、另一条仍会「假绿」**。
  ⇒ 同值同形的多行，**把行尾注释一起写进正则**；改完后顺手检查同一字典里是否还有别的宽松条目。
- **C2 段（殿堂点数顺序专项）** ⭐：把「模板 `fixed_stat_*` 的字面量」与「入口文件 `hero_data.stats` 的数组」交叉比对，断言数组 == `[health, attack, range, speed]`。
  ```
  stats 数组顺序 = {生命, 伤害, 射程, 速度} —— 由 hero_room_view 的 hero_room_stats 子节点顺序决定
  （hero_room_stat_health → stat_damage → stat_range → stat_speed；screen_map.lua 按 children 下标 set(hd.stats[i])）
  ```
  **踩过的真坑**：定值必须**按语义名对号入座**，而不是按"你想到的顺序"写。johnny_deadeye 最终定值 = `stats = { 3, 7, 8, 6 }`（生命3 / 伤害7 / 射程8 / 速度6），对应模板 `fixed_stat_health=3 / attack=7 / range=8 / speed=6` —— 数组第 1 格是**生命**，所以 `attack` 的值 7 落在第 2 格。曾经把 `fs.attack` 放在第 1 格（生命位）→ 殿堂里生命/伤害两行数值互换（用户报"攻击和生命反了"）。**这个顺序不报错、且 Dove 的殿堂里没有任何行标签/图标**（`HeroStatDots` 只会画 8 个点，`heroroom_bg` 里也没有图标），肉眼看不出顺序 → **只能靠 §C2 这种把「模板 fixed_stat_* 字面量」与「hero_data.stats 数组」交叉比对的断言守住**（改成按语义名展开：`[health, attack, range, speed]`）。另注：`hero.fixed_stat_*` 在 Dove 引擎里**无人消费**（真正决定显示的是 `hero_data.stats`），别以为改了模板字段就生效。

