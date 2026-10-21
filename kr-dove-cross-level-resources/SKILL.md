---
name: kr-dove-cross-level-resources
description: 在《王国保卫战 Dove》(KingdomRushDove) mod 中复用其他关卡的模板/特效时，强制加载其贴图组、exo 骨骼动画与动画帧，并防卸载，避免非本关运行时报 `exo_frame called: nil`、`Sprite ... was not found`、`render_utils.lua attempt to index local 'ss'` 等错误。也含反向排查：自建关卡 `required_textures` 该填哪些图集组（scripts/find_level_atlases.py）、脚本动态创建的特效粒子与敌人音效缺组（scripts/audit_level_resources.py，覆盖 `Sprite fx_water_bubble_* was not found`、`SOUND XXX defined but sound sources missing`）、插件关卡 `MusicBattle_00 NOT FOUND` 的修正、以及 `animation X not found` + `Sprite nil was not found` 的动画名不匹配排查（含本体硬编码裸 `idle` vs 模板只有 `idle_a/_b` 的缺陷模式）、`Failed to load atlas bytecode: xxx.luac` 的假组名识别。另含**动画键与帧率的通用硬规则**：`ranges` 的两种格式语义（`#==2` 区间含两端 vs `#>2` 逐帧列表）、稀疏抽帧补速（模板 `sprites[i].fps = 30÷抽帧比`，禁写进 ANIM_DEFS）、运行时动画键 `prefix_name` 与注册键 `prefix_size` 的两侧逐字命中规则、`animated=true` 必须显式设 `name`、KR1 图集 `alias` 必须展开。触发场景：mod 里 `E:create_entity("某关卡的子弹/特效/单位")`、复用关卡专属动画/贴图、进关满屏 Sprite 找不到、进关报某音效 missing、自定义关卡没有战斗音乐、召唤英雄/士兵后动画报 not found、动画播放速度不对/偏快、动画键查不到、`animation X not found`；以及**插件侧（英雄/塔全关卡通用）**跨关卡依赖：`create_entity` 关卡专属模板必须自己 `require("kr1.template_groups.levelNNN_templates")`（否则 `entity_db.lua:11 pairs(nil)` 崩，报错栈是 `quickcopy ← create_entity ← 插件脚本`）、`S:queue` 的音效组要在 `director.load_sound_groups` 现场注入（`scripts/find_sound_group.py` 反查组名）、`plugin_required_exoskeletons` 只装插件自带 exo。参考范本：mods/local/boss_crocs_hero、mods/local/boss_bull_king_hero。
agent_created: true
---

# Kingdom Rush Dove 跨关卡资源强制加载

## 问题背景

游戏资源分三层，均**按关卡加载、切关卸载**（104 关等非 103 关没有 103 关的资源）：
1. **贴图层**：贴图组（`_assets/<target>/images/<size>/go_XXX.lua` 清单，如 `go_stage103`），非本关时 `I:s(name)` 返回 nil → `render_utils.lua:403 attempt to index local 'ss' (a nil value)` + `image_db.error Sprite ... was not found`。
2. **exo 层**：骨骼动画数据（`kr1/data/exoskeletons/XXX.lua`），非本关时 `EXO:f(fn)` 查不到 → `exoskeleton.error f() - Could not find exo_frame called: nil`。
3. **动画层**：`A.db`（animation_db）——`A:load()` 首次执行时**整表重置**（`animation_db.lua:90-97`，loaded 守卫只执行一次），早于它注册的动画会被清掉。

## 标准解法（照 boss_crocs_hero）

hook `director.load_texture_groups`（`plugin/all/hook_utils.lua` 的 HOOK 机制），在 `item_name == "game"` 时：

```lua
local STAGE03_TEXTURE_GROUPS = { "go_stage103", "go_stage103_bg", "go_enemies_sea_of_trees", "go_stages_sea_of_trees" }

function hook.director.load_texture_groups(load_texture_groups, self, groups, texture_size, ref_height, queue, item_name)
    if groups and item_name == "game" then
        -- 1) 贴图层：去重追加目标关卡贴图组，引擎随即 I:load_atlas_new/queue_load_atlas 加载进 atlas
        for _, tex in ipairs(STAGE03_TEXTURE_GROUPS) do
            local has = false
            for i = 1, #groups do if groups[i] == tex then has = true break end end
            if not has then groups[#groups + 1] = tex end
        end
        -- 2) exo 层：排队，引擎在关卡流程 EXO:load()（A:load() 之后）统一加载注册，时序天然正确
        local EXO = require("all.exoskeleton")
        EXO:queue_load({ "explosionDef" })
        EXO.exos_count["explosionDef"] = 999999  -- 防卸载：EXO:unload 按计数递减永不归零
    end
    return load_texture_groups(self, groups, texture_size, ref_height, queue, item_name)
end
-- hook:init 里：
--   local ok, director = pcall(require, "director")
--   if ok and director then HOOK(director, "load_texture_groups", hook.director.load_texture_groups) end
-- unload 里对应 UNHOOK。
```

## ⭐⭐ 插件侧（英雄/塔，全关卡通用）跨关卡资源三件套

英雄/塔**全关卡都可选**，但资源**按关卡加载**。插件模板本身在 `hook.E.load` 注册（进 `entities` 与首次备份），
贴图/exo 也能照上面的方式强制加载 —— 但还有两块**最常漏**：

| 缺的东西 | 症状 | 修法 |
|---|---|---|
| **实体模板**（关卡专属 `kr1/template_groups/levelNNN_templates.lua` 里的） | ① `all/entity_db.lua:11 bad argument #1 to 'pairs' (table expected, got nil)`，栈 `quickcopy ← :359 create_entity ← <插件脚本>`；② **若它只是"派生模板的父模板"** ⇒ 派生模板静默不注册 ⇒ `create_entity` 拿 nil 被 `pcall` 吞掉 ⇒ **技能完全无输出、零报错** | 在 `hook.E.load` 里 `require("kr1.template_groups.levelNNN_templates")`，**且要排在派生模板注册之前** |
| **声音组**（音效归属的 `groups.lua` 组） | `sound_db.error play() - SOUND X defined but sound sources missing` | HOOK `director.load_sound_groups(self, groups)`，现场把组名塞进 `groups` |

### 1) 实体模板：自己 require，且时序只能是 `hook.E.load`

`entity_db.entities[t] == nil` 时 `create_entity(t)` → `quickcopy(tpl)` 首行 `pairs(nil)` 崩（`all/entity_db.lua:9-15` / `:359`）。
关卡专属模板只在那一关由 `all/systems/level.lua:76-84` 加载；英雄全关卡通用 ⇒ **必须在插件侧自己补**：

```lua
local REQUIRED_TEMPLATE_GROUPS = { "level131_templates" }

local function ensure_entity_templates()
    for _, grp in ipairs(REQUIRED_TEMPLATE_GROUPS) do
        local ok, err = pcall(require, "kr1.template_groups." .. grp)
        if not ok then log:warning("[entry] template group %s failed: %s", grp, tostring(err)) end
    end
end
-- 调用点：hook.E.load(load, self) 里 load(self) 之后（crocs :321 / bull_king :215）
```

- **为什么这个位置就对**：`entity_db:Load()`（`:28-43`）首次先 `self:load()`（我们的 hook 包着它）→ 再 `self:precompile()`
  → 最后 `self.entities_backup = quickcopy(self.entities)`。我们注册在 `load()` 之内 ⇒ **进了首次全量备份** ⇒
  之后每次 `Load()`（`table.clear` + 从备份恢复）都带着它，**即使它是 `register_t_hot(name, base, true)`（is_tmp=true）也照样持久**
  （is_tmp 只影响 `precompile_hot` 是否回写备份，见 `:265-266`）。
- ⚠ 别把 require 挪到关卡 `level:init`、`hook:unload`、或"首次放技能时惰性加载"——`E:Load()` 只有**首次**会调 `load()`，
  挪出去就是"某些关卡偶发崩"。
- ⚠ **只对"关卡专属模板"需要**。插件自己的模板（`E:register_t`）、`all/templates.lua`、`kr1/game_templates.lua`、
  `kr1/boss.lua`（`kr1/game_templates.lua:35 require("boss")`）都常驻，别多此一举。
  判断法：`grep -rln '"<模板名>"' all kr1` —— 只命中 `kr1/template_groups/levelNNN_templates.lua` 才是关卡专属。

#### ⭐⭐ 2026-10-10 实证：`boss_crocs_hero`「酸液冲击」完全不出弹（零报错）

**现象**：技能照常进冷却、无任何报错，但**一颗子弹都不出**（离线断言 `E:create_entity("bullet_boss_crocs_wraith_wrath") == nil`）。

**根因链**（三步，缺一不可）：
1. 插件 `hero_templates.lua` 注册酸液弹用的是**守卫式派生**：
   `if E:get_template("bullet_stage_03_heart_of_the_arborean") then E:register_t("bullet_boss_crocs_wraith_wrath", 它) end`
2. 该父模板**原本是全局常驻**（2026-08-22 记录：`kr1/game_templates.lua:9485`），**Dove 更新后已挪进
   `kr1/template_groups/level103_templates.lua`（关卡 103 专属）** ⇒ 首次 `E:Load()` 时库里没有它。
3. 首次 `E:Load()`（`all/systems/level.lua:72`）**早于**该关 `required_templates` 的 require（`:76-84`）⇒ 判定必失败
   ⇒ 派生模板不注册 ⇒ 技能脚本 `pcall(E:create_entity(...))` 静默吞掉 nil ⇒ 零输出。

**两处硬规则**：
- ⭐⭐ **"某原版模板常驻"是会随 Dove 更新失效的假设** ⇒ 引用前必须复核归属：
  `grep -rn '"<模板名>"' kr1/game_templates.lua`（命中=常驻）/ `kr1/template_groups/*.lua`（只在这里命中=关卡专属）。
- ⭐⭐ **`ensure_entity_templates()` 必须排在"派生模板注册"之前**。crocs 原来的顺序是
  `require hero_templates → ensure_entity_templates()`，**正好反了**（`require` 一执行就判定失败）。
  凡插件里有"守卫式派生"，① 加载组要早于守卫；② **守卫失败必须 `log:warning`**（静默是最大风险），
  ③ 更稳的写法是在守卫处兜底再 require 一次：
  ```lua
  if not E:get_template(PARENT) then pcall(require, "kr1.template_groups.level103_templates") end
  if E:get_template(PARENT) then ... register ... else log:warning("parent %s missing", PARENT) end
  ```
- 顺带：该弹命中音效 `Stage03HeartOfTheForestBlast` 属**声音组 `stage_03`**（用 `scripts/find_sound_group.py` 反查）⇒ 记得补进 `REQUIRED_SOUND_GROUPS`。
- 复现/回归验证：`.workbuddy/probe_crocs_acid.lua`（离线 harness，21 断言：父模板缺失复现 + 补齐后注册 + `create_entity` 出弹 + 入口源码顺序断言）。

#### ⚠ `plugin_required_exoskeletons` 装不了引擎 exo（别指望它治"模板缺失"）

新接口 `EXO:queue_load_plugin(list)` 要求每项带 `path="plugins/..."`（`all/exoskeleton.lua:41` 直接拿它拼路径）
⇒ **只适用插件自带 `.exo3`**。本体引擎 exo（`stage_31_fireball_ADef` 之类）仍走老接口 `EXO:queue_load({...})`。
**「实体模板缺失」和「exo 骨骼缺失」是两码事**，报错文案也不同，别混。

### 2) 声音组：改 `game.required_sounds` 没用，要在 director 现场注入

`S:queue("X")` 只认 `sound_db.sources[文件]`；组没加载就没有源 → "defined but sound sources missing"。
`director.lua:497` 调 `self:load_sound_groups(game.required_sounds)` 时**已经读过那张表**，
所以「在 `hook.E.load` 里追加 `game.required_sounds`」对**首关没用**（只对后续关卡生效，症状是"第一关报错、第二关就好"）。

```lua
local REQUIRED_SOUND_GROUPS = { "stage_35", "stage_31", "enemies_terrain_wukong_3" }

local function inject_sound_groups(groups)
    if not groups then return end
    for _, grp in ipairs(REQUIRED_SOUND_GROUPS) do
        local found = false
        for i = 1, #groups do if groups[i] == grp then found = true; break end end
        if not found then groups[#groups + 1] = grp end
    end
end

function hook.director.load_sound_groups(load_sound_groups, self, groups)
    inject_sound_groups(groups)
    return load_sound_groups(self, groups)
end
-- hook:init: HOOK(director, "load_sound_groups", hook.director.load_sound_groups)
```

- 传进来的 `groups` **就是 `game.required_sounds` 本体**；追加后关卡卸载按同一张表递减引用计数，账目自动平衡
  （`all/sound_db.lua:219-242` 有 `sounds_uses` 引用计数 + 组去重，重复注入不会重复加载）。
- 全部 493 个组在 sound_db 初始化时一次性注册（`all/sound_db.lua:148-150` `FS.load(...groups.lua)()`），
  `queue_load_group(name)`（`:182`）只做"按名加载"，查不到才报 `sound group %s not found` ⇒ **追加组名即生效**。
- **组名怎么查**：`python scripts/find_sound_group.py <KingdomRushDove 根> --plugin <插件目录>`（本 skill 自带）。
  原理：`sounds.lua`（音效 ID → ogg 文件名）+ `groups.lua`（组 → ogg 文件名）**用 ogg 文件名做桥**。
- ⚠ **组名不在 `sounds.lua`**：那里每条只有 `source_group="SFX"/"SPECIALS"`（openal 源池分类），与"组"无关。
- ⚠ 一个音效常在**多个组**里有同名 ogg（如 `TerrainWukongMeteoriteImpact` 在 `stage_31`/`stage_32`/`stage_35`）
  ⇒ 取一个最小的即可，多注入只是白花显存。
- ⚠ 音效可能来自**本体模板的 `sound_events`**，不在插件脚本字面量里 ⇒ 脚本扫不出来。
  例：crocs 的 `Stage22AbominorAcidHit` 来自 `kr1/game_templates.lua:8950` 的
  `bullet_boss_crocs_poison_rain_lvl1`（`tt.sound_events.hit = ...`）—— 要顺着"英雄会 create_entity 哪些本体模板"去查。

### 3) 别忘同步两侧 + 重启

- 插件实际运行的是 `%APPDATA%/LOVE/kingdom_rush_dove/plugins/<entry>/`（`plugin/plugin_main.lua:7-9` 的 `FS.setRequirePath`）。
  **只改 dev `mods/local/` 不推 AppData = 不生效**。同步：`.workbuddy/compare_plugin_sync.py <entry> --push <点名文件>`
  （方向 dev→AppData，绝不整目录覆盖；`config.lua` 被游戏写 `last_used_at`，DIFF 正常，别推）。
- 模板/数值进程内只烤一次 ⇒ **必须重启游戏**；插件若因报错被游戏自动禁用，还要**手动重新启用**。
- 参考实现：`mods/local/boss_crocs_hero/boss_crocs_hero.lua`（模板 :105/:321、音效 :119/:263）、
  `mods/local/boss_bull_king_hero/boss_bull_king_hero.lua`（模板 :72/:215、音效 :86/:263）。

## 关键注意事项

- **查贴图组名**：目标关卡的 `required_textures` 在 `kr1/data/levels/levelXXX_data.lua`（单行文件，用 python 正则 `required_textures\s*=\s*\{[^}]*\}` 提取）；用 `grep -c "<贴图名>" <组>.lua` 验证缺失贴图确实在该组。
- **查 exo 名**：特效模板里 `render.sprites[1].exo = true` 的动画 = `kr1/data/exoskeletons/<前缀>.lua`（如 prefix "explosionDef" → explosionDef.lua，动画名 `explosionDef_idle`）。103 关等关卡的 `required_exoskeletons` 列表可直接参考。
- **手动兜底注册 exo**（若 director hook 不可靠）：`EXO:load_lua("explosionDef")` + 仿 `EXO:load()` 逻辑注册动画到 `A.db`/`EXO.db`。**成功判据必须双条件**：`EXO.exos[name]` 存在 **且** `A.db[name.."_idle"]` 存在；失败要 `EXO.exos[name] = nil` 回滚，否则 director 通道的 `EXO:load()` 见 exos 已存在会跳过加载，动画永远缺失。调用时机放在**关卡内**（如控制器协程 init），确保 `A:load()` 已执行、注册不会被重置。
- **require 路径**：`require("all.exoskeleton")`（引擎同款，director.lua:22）；`require("animation_db")`（引擎 render.lua 同款）。main.lua search_roots 含 "all"，`require("exoskeleton")` 也会解析到同一文件，但显式写 all. 更稳。
- **防卸载**：`EXO.persistent_exos` 是 exoskeleton.lua 模块内 local 表，mod 改不到；用 `exos_count[name] = 999999` 顶高等效（unload 递减永不归零）。
- **动画层时序**：任何对 `A.db` 的手动注册必须在 `A:load()` 首次执行之后，否则被 `self.db = FS.load(...)()` 整表重置清掉。

## 反向排查：自建关卡到底该登记哪些图集组

**症状**：自己做的关卡（插件关卡）进关后满屏
`image_db.error s() - Sprite orc_0045 was not found in the atlas db.`（帧前缀 + 4 位序号，一次刷几十条），
根因是关卡 `data/levels/<L>_data.lua` 里 `required_textures = {}` 是空的。

**一键推导**：`python scripts/find_level_atlases.py <KingdomRushDove 根> <该关的 _waves_campaign.lua>`（本 skill 自带）。手工步骤：

1. **取敌人**：波文件里 `creep = "xxx"` 的取值就是敌人模板名（编译态字段名是 `creep`，**不是** `template`）。
2. **取真实帧前缀**：在 `kr1/data/game_animations.lua` 里找属于该模板的动画键，读它的 `prefix`。
   ⚠️ **模板文件里的 `render.sprites[1].prefix = "enemy_bandit"` 不是帧前缀**，那只是"动画命名空间"（恰好等于模板名）；真实帧前缀是 `bandit`（帧名 `bandit_0001`…）。用错就永远查不到组。
   ⚠️⚠️ **动画键必须按"最长模板名前缀"归属**。直接 `key:startswith(creep.."_")` 会吞掉别人的键：`enemy_cannibal` 会匹配到 `enemy_cannibal_volcano_*`，而那是 level36 火山关的**独立模板** `enemy_cannibal_volcano`（帧 `Stage9_Beast` 在 `go_stage36`）→ 平白多加载几十 MB。同理 `enemy_wasp`/`enemy_wasp_queen`、`enemy_gorilla`/`enemy_gorilla_small`。脚本已按最长前缀实现。
3. **查组**：在 `_assets/kr1-desktop/images/fullhd/go_*.lua` 里用正则 `[{,]\s*<prefix>_\d{4}\s*=` 定位 → 该前缀所属组（可能多组，取并集）。
4. **扣常驻组**：`all/game.lua` 的 `game.required_textures` 无条件加载（`go_decals`/`go_enemies_common`/`go_editor`/`go_towers_group1..25`/`go_stage128`/`tower_holders`），不要去重登记。
5. **地形变体另算**：带特殊地形的模板会是**另一个模板**（不是同一模板的状态），例如 `enemy_cannibal_volcano_normal`（level36 火山关，需要 `go_stage36`）。只看 `creep` 列表里有没有这个模板名即可，不必自己推地形；`SU.enemy_water_change`（all/script_utils.lua:3019）按 `GR:cell_type` 切水域动画，所以水/火山地形才需要对应图集。
6. **写进关卡数据**：

```lua
required_textures = { "go_enemies_acaroth", "go_enemies_bandits", "go_enemies_grass", "go_enemies_jungle" },
```

- **元素是纯字符串组名**，与 `plugin_required_textures`（`{path=..., use_bytecode=...}` 表、会被加上 `plugins/` 前缀）不是一回事。**游戏本体的图集不能走 plugin 通道**，必须走 `required_textures`。
- 链路：`all/level_utils.lua:94-114` 把 `level.data.required_textures` 拷进 `store.level.required_textures` → `all/director.lua:481` `load_texture_groups(..., "game")` → `I:load_atlas_new(scale, KR_PATH_ASSETS_GAME_TARGET.."/images/"..texture_size, group)`。

## 插件关卡的 `SOUND WITH ID MusicBattle_00 NOT FOUND`

自定义关卡走 `director.lua:451-458` 分支，固定 `game.store.level_idx = 0`；而 `game_gui.lua:169` / `all/game.lua:257,302` / `game_gui.lua:4228` 会 `S:queue(string.format("MusicBattle_%02d", level_idx))` → 拼出根本不存在的 `MusicBattle_00`（`_assets/kr1-desktop/sounds/sounds.lua` 里只有 `MusicBattle_01..140` 等）。

**正确解法**：写关卡自己的 `data/levels/<L>_metadata.lua`（启动器/关卡选择读它，转成 `custom_battle_music` / `custom_battle_prep_music` 传进 director）：

```lua
return {
    thumbnail_sprite = nil,
    thumbnail = "assets/images/热带回环.png",
    battle_music = "MusicBattle_37",              -- Jungle_Battle.ogg
    battle_prep_music = "MusicBattlePrep_37",     -- savage_music_jungle_preparation.ogg
    category = "normal"
}
```

- 链路：`all/screen_custom_map.lua:140-141`（读 metadata）→ `:1215-1216`（作为 args）→ `director.lua:456-457` → 各处 `if store.custom_battle_music then ... else %02d end`。填了走定制曲，没填就吃 `_00` 报错。
- 等价写法：在关卡脚本 `level:init(store)` 里直接 `store.custom_battle_music = "..."`（`mods/local/ZHAO_ZE_DI_XUE` 就这么写）。二选一即可，metadata 更声明式。
- 挑曲方法：`sounds.lua` 里条目自带文件名，如 `MusicBattle_37={files={"Jungle_Battle.ogg"}}`、`MusicBattle_32=Desert_Battle.ogg`、`MusicBattle_14=MusicBattleUnderAttackForest1.ogg`。

## 反向排查 2：脚本动态创建的特效粒子 & 敌人音效缺组

**症状**（沼泽地穴关实测）：
- `image_db.error s() - Sprite fx_water_bubble_big_projectile_0001 ... was not found in the atlas db.`（0001~0016 刷一遍）
- `sound_db.error play() - SOUND EnemyRazingRhinoDeath defined but sound sources missing.` / `SOUND RTWaterExplosion ...`

**为什么 `find_level_atlases.py` 查不出来**：它只看敌人本体/子弹的帧。鳄鱼系敌人是在
`scripts.enemy_crocs_basic.insert` 里 **动态拼名** 造粒子的：

```lua
local size_names = {"small", "small", "big"}
local e2 = E:create_entity("ps_enemy_crocs_water_bubbles_" .. size_names[this.unit.size])
-- this.water_trail_with_bubbles_projectile 时还会再建 ps_enemy_crocs_water_bubbles_projectile
```

模板 → 帧的映射链：`ps_enemy_crocs_water_bubbles_projectile.particle_system.name = "fx_water_bubble_big_projectile"`
（`kr1/game_templates.lua:15107`）→ `game_animations.lua` 的 `fx_water_bubble_big_projectile = {from=1, prefix=..., to=16}`
→ 帧只存在于 **关卡图集** `go_stage121` / `go_stage122`（`go_enemies_*` 里没有 FX 帧）。

**一键核查**：`python scripts/audit_level_resources.py <KingdomRushDove 根> <该关 _waves_campaign.lua> [<该关 _data.lua>]`
（本 skill 自带，会同时给出"要补的音效组"和"要补的帧前缀+候选组"，并列出动态拼名的实体提醒人工确认；
拿一份"未修复的 _data.lua"跑它，能 1:1 复现上面两条报错）。

**结论速查（沼泽地穴 / 鳄鱼关）**：

| 缺的东西 | 帧 / 文件 | 该登记的组 |
|---|---|---|
| 涉水气泡、水花 | `fx_water_bubble*`、`fx_water_splash*`（62 帧） | `go_stage121`（1 张 8MB dds）或 `go_stage122`（2 张 32MB）——**两者这 62 帧美术完全一致，优先登 121** |
| 鳄鱼坦克死亡音 `EnemyRazingRhinoDeath` | `kra_sfx_enemy_razingRhino_death_v1.ogg` | `stage_22`（或 `enemies_sea_of_trees`）|
| 子弹落水音 `RTWaterExplosion` | `Explosion_water.ogg` | `stage_22`（或 `RisingTidesSounds`）|

```lua
required_sounds = { "music_stage120", "enemies_terrain_crocs", "stage_22" },
required_textures = { "go_enemies_grass", "go_enemies_terrain_5", "go_stage121" },
```

**踩坑记录**：
1. **别用非贪婪正则解析 `groups.lua`**。`([A-Za-z0-9_]+)=\{files=\{(.*?)\}\}` 会跨组误判，
   实测把 `stage_22` 的文件误报成在 `common` 里，于是以为"常驻已覆盖"而漏补 → 依旧报缺音效。
   必须用花括号配对取 body。（同理解析 `sounds.lua`：它是单行 `return {ID={files={...}},ID2={...}}`，
   用 `\n\t` 开头的正则一条都匹配不到。）
2. **搜文件名要用完整文件名**，不能用子串：`razingRhino` 会命中 `razingRhino_basicAttack/charge`，
   从而误判 `common` 里已有死亡音（实际没有）。
3. **`common` 组不是万能的**：它只有 413 个常见 ogg，各关专属音（Rhino 死亡、落水爆炸）不在里面。
   官方 level122 的 `required_sounds` 就明确写了 `stage_22`，照抄最稳。
4. **同名帧存在多个组时优先取 dds 体积小的**（`_assets/assets_index.lua` 里能查到每个 dds 的字节数，
   或直接 `ls -la` 对比）。别为了"忠实于原关卡"多背 24MB 显存。
5. **水迹线不是关卡图集的**：`ps_water_trail` 的 `particle_system.name = "UnderwaterParticle2"` 也在
   `go_towers_group6`（常驻），所以它不会报错；带 `_bubbles_` 的才会。
6. **资源在 appdata 与工作区两份，改完要同步**：工作区 `mods/local/<L>/data/levels/<L>_data.lua`、
   其大写副本（如 `mods/local/ZHAO_ZE_DI_XUE/`）、以及游戏实际读的
   `%APPDATA%\LOVE\kingdom_rush_dove\plugins\<L>\...`；改完用 `.workbuddy/lua_syntax_check.py` 过语法。
7. 源码侧索引：`Fx_Shaman_BlocktowerDef`、`Tank_crocs_animationsDef`、`hydra_unitDef` 这类以 `Def` 结尾的
   名字是 **exo 骨骼**（登记到 `required_exoskeletons`），在 `go_*.lua` 里当然找不到，别当成"贴图缺失"。

## 反向排查 3：`animation X not found` + `Sprite nil was not found` —— 动画名不匹配（本体缺陷，别去补贴图组）

**症状（成对出现，顺序固定）**：
```
animation_db.error fn() - animation denas_hero_idle not found
image_db.error s() - Sprite nil was not found in the atlas db.
```

**判据**：`Sprite` 的名字是 **`nil`**（不是某个帧名）⇒ 不是贴图缺组，而是**动画名查不到** → 帧名取不到 → sprite 名变 nil。
一看到 `Sprite nil` 就别再查 `required_textures` 了，转查动画键。

**排查三步**：
1. **从报错名拆 prefix**：报错名 = `<prefix>_<后缀>`。用
   `grep -ao "<前缀>[a-z0-9_]*" kr1/data/game_animations.luac | sort -u`（**动画库是 .luac，用 grep 提取字符串**）
   列出该前缀所有合法动画键。
2. **对比模板实际提供的**：模板在 `kr1/game_templates.lua`（明文）里 `render.sprites[1].prefix = "..."`；
   再搜同目录/`kr1/template_groups/` 找显式动画引用（`melee.attacks[n].animation`、`idle_flip.last_animation`、
   `arrived_slot_animation`）。
3. **定位硬编码调用点**：`awk '/^function |^local function /{fn=$0} /"<裸名>"/{print NR": ["fn"] "$0}' all/script_utils.lua`
   —— 直接给出「哪行、在哪个函数里」硬编码了这个裸名。

**已确认实例（2026-09-30，迪纳斯 Denas）**：本体缺陷，任何 mod 召唤 Denas 都会命中。
- `kr1/game_templates.lua:9075` `soldier_reinforcement_stage_15_denas`（派生自 `soldier_militia`），
  `prefix = "denas_hero"`；动画库只有 **`denas_hero_idle_a` / `denas_hero_idle_b`**（**无裸 `denas_hero_idle`**）。
- `kr1/game_scripts.lua:23504` 的 Denas 专属脚本内部 idle 全用 `idle_a`/`idle_b`（正确），但 **23608 行**
  把非 area 攻击转调通用 `SU.y_soldier_do_single_melee_attack`。
- `all/script_utils.lua:2505`（`SU.y_soldier_do_single_melee_attack` 结尾）**硬编码**
  `U.animation_start_default(this, "idle", ...)` → 查 `denas_hero_idle` → 失败。
- 对照：基类 `all/templates.lua:892` 有 `soldiermilitia_idle`（裸名存在）⇒ 同一段通用代码对普通士兵无害。
  `all/script_utils.lua` 里共 12 处硬编码裸 `"idle"`。

**顺带排查同屏的另一条 error**：若同时出现
`preload_atlas_from_bytecode() - Failed to load atlas bytecode: _assets/<target>/images/fullhd/<组名>.luac. Error: nil`，
说明关卡 `required_textures` 登记了**不存在的组名**（`_assets/assets_index.lua` 里查不到即为不存在）。
先查同名字符串在整个游戏里的真实归属，常常发现帧其实在**常驻组**（`all/game.lua:30-63` 的
`go_decals`/`go_enemies_common`/`go_editor`/`go_towers_group1..25`/`go_stage128`/`tower_holders`）里
⇒ 那行**无效且多余**，直接删（例：`kr4_warmongers_tower_mage` 不存在，而 `warmongers_mage_tower*` 帧在常驻 `go_towers_group25`、
`warmongers_archer_tower*` 在 `go_towers_group23`）。


## 动画键与帧率的通用硬规则（2026-10-01 从工作区 MEMORY 迁入）

> 这三条是**任何**自制/移植单位的动画必修课，与具体关卡无关。

### ⭐⭐ `ranges` 两种格式语义不同

`animation_db.extract_frame_from`（`all/animation_db.lua:29-55`）：

- `#range == 2` → **`from, to` 区间**（含两端，`to < from` 自动反向）
- `#range > 2` → **逐帧显式列表**

即 **`{1, 36}` = 36 帧**（**不是** 2 帧）、`{1,4,7,...,61}` = 21 帧。
⚠ 别按「数端点」理解成 2 帧。

### ⭐⭐ 补速：引擎按「逻辑帧」播，与图集实存帧数无关

引擎播动画 = **「1 逻辑帧 = 1/30 秒」**（`animation_db:fn` 的 `time_offset * fps`），
与「图集实际存了多少张图」**无关**。⇒ 稀疏抽帧（如每 3 帧取 1）照 30fps 播会**快 2~3 倍**。

**修法** = 模板 `render.sprites[i].fps`（`render.lua:345`）= **30 ÷ 抽帧比**。

- ⚠⚠ **绝不能写进 `ANIM_DEFS`** —— `register_animations` 只保留 `{frame_count, frame_names}`，`fps` 会被丢弃。
- ⚠ `motion.max_speed` 与 `fps` **无关**：前者是**位置**移动速度，后者是**帧序列**播放速度。
- **原帧号搬运（非抽帧）时 `fps = 30`。**
- ⚠ 整条 sprite 只有**一个** `fps` 字段 ⇒ 混合段落（多数全帧 + 少数抽帧）只能取折中值
  （ember 即取 30，仅 `volcano_rising` 偏快）。

### ⭐⭐ 动画键两侧必须逐字命中

- **运行时键** = `sprites[1].prefix .. "_" .. name`（`render.lua:345`），
  `name` 被 `size_names[unit.size]` 替换（`script_utils.lua:1134`）
- **注册侧**按**字典 key**（`animation_db.lua:84-88`），帧名用 `prefix .. "_%04i"`（`:27`）
- ⇒ **注册 key == `prefix_size`；注册 prefix == 图集帧名前缀**

**两个高危混淆点**：

1. ⚠ **模板 `render.sprites[i].prefix` 与注册 prefix 是两回事**
   （前者拼**运行时键**，后者查**图集**）。
2. ⚠ **照抄原版模板不一定对**：原版毒蛇 `prefix="viper"` 因**原版图集**帧名是 `viper_%04i`；
   自制图集是 `viper_poison_%04i` ⇒ 必须写 `"viper_poison"`。
3. ⚠ **附属图可能叠在别的命名空间**：ember 岩浆的真实图集前缀是
   `hero_ember_ability-1_magma`（**不是**动画表里看到的 `hero_ember_magma`）
   ⇒ **先 grep 图集实际帧名，再定 prefix 与 key**。

### ⭐⭐ `animated = true` 的 sprite 必须显式设 `name`

sprite 组件**默认 `name="idle"`**（`components.lua:180`），
运行时键 = `prefix .. "_" .. name` ⇒ **只给 prefix 不给 name** 会去查 `prefix_idle`，
未注册即报 `animation X not found` **+ 紧跟** `image_db:s - Sprite nil`（**两条同源，别当两个 bug**）。

- 原版 `power_scorched_water` 也显式设了 `name="fireball_vapor"`（`templates.lua:1052`）。
- 原版 `aura`/`lava` 基类不带 render 才免于此。

### ⭐ KR1 图集 `alias` 已被 `image_db` 自动解引用（2026-10-03 更正旧结论）

`alias = { "下一帧名" }` 是「**共享同一张图**」的指针。
`lib/klove/image_db.lua:507-510`（`load_atlas_new` 帧表路径）与 `:563-568`（另一条帧表路径）
都做 `self.db_atlas[v.alias[i]] = self.db_atlas[k]` ⇒ **Dove 会把 alias 目标名注册成指向同一 quad**。

- ⇒ 重制版 `go_hero_*` 图集只存**奇数帧**、偶数帧用 alias 指过来；**原样（verbatim）照搬 + 原版连续 `ranges` + `sprites[i].fps = 30`** 就是逐帧一致（zezitra 实证），**不必展开**。
- 展开成独立条目**也不错**（只是多几条 `db_atlas`），ember 那套展开式写法可继续沿用。
- ⚠ 旧结论「Dove 的 `image_db` 不做 alias 解引用」是 2026-10-01 的误判，**已作废**。
- ⚠ 但 `db_atlas` 是**全局键空间**：跨图集同名键后者覆盖前者 ⇒ 插件图集里的通用帧名（`rage_small_0001`、`finalBoss_guy_ray*` 等）必须改名，**alias 目标名要同步改**。

### 验证脚本

`.workbuddy/check_ember_anim_keys.py` —— 动画键两侧逐字命中
（注册前缀 ↔ 图集帧名，注册键 ↔ 模板运行时名）。
⚠ **文本解析法**：插件注册动作挂在 `hook.A.load`/`hook.E.load`，`require` 本身不触发；
且 `love_stub` 会把 `animation_db` 顶成假表 ⇒ 只能抠源码文本比对。
