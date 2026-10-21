---
name: kr-dove-stage-hero-port
description: 把《王国保卫战 Dove 版》的舞台英雄（stage_hero，如 218 关 hero_stage_218_denas）移植为局外可选英雄插件的成套步骤与必背坑：模板派生并删舞台标志、花名册三处注入（map_data.hero_data 缩略图 / hero_room_view 插 portrait_<名> 大立绘且须在 portrait_hero_name_label 之前 / strings.hero_room_special 殿堂技能介绍，loaded 优先 + type 校验 + E.load 钩子时机）、入口文件必须 return hook（否则 plugin_main.lua:72 静默跳过）、舞台模板全无的经验系统三件套（xp_gain_factor / SU.hero_level_up 每帧结算 / fn_level_up 必须幂等）、update 必须包成外层协程（引擎只 create 一次、每帧 resume 同一个 ⇒ "每帧覆写"是幻觉）、未解锁技能用每帧顶 ts 且禁用 ts=tick_ts（会让 auto_rally 失效）、护甲走 health.raw_armor + SU.update_armor、回满血 = hp_max × GS.soldier_regen_factor、召唤物 controable=true 走 F 键原生调集、必补 vis.flags |= F_HERO。触发词：舞台英雄移植、stage_hero、hero_stage_218_denas、可选英雄、殿堂大立绘空白、殿堂技能介绍没字、hero_room_special、经验不涨、升级不结算、fn_level_up、技能永远不发动、自动调集失效、hero_denas_warlord。
agent_created: true
---

# 舞台英雄 → 可选英雄移植配方（kr-dove-stage-hero-port）

把 KR/Dove 的**舞台英雄**（`stage_hero`，如 218 关 `hero_stage_218_denas`）移植为**局外可选英雄插件**的成套步骤与必背坑。

**参考实现（全机制实测通过）**：`mods/local/hero_denas_warlord/`（2026-10-14，含等级成长 / 经验系统 / 召唤物三档 / F 键调集）。

---

## 步骤清单

1. **模板派生**：`E:register_t("<新名>", "<舞台模板>")` —— quickcopy 深拷贝，删舞台标志（`tt.hero.stage_hero = nil` 等）不影响本体。
2. **花名册注入（三处，缺一不可）**：
   - `map_data.hero_data` 插条目 → 缩略图网格（`screen_map.hero_data` 是同表引用，`screen_map.lua:234`；殿堂遍历在 `:6588`）；
   - HOOK `kui_db.get_table` 往 `hero_room_view` 模板的 `hero_portraits` 节点插 `portrait_<名>` 大立绘条目——`show_hero` 按 `"portrait_"..名` 匹配（`screen_map.lua:6766`），必须插在 `portrait_hero_name_label` **之前**（防名字被盖）。缺则点进去大立绘全 hidden 空白。
   - **殿堂「技能介绍」**：`strings.hero_room_special[英雄名] = { [技能名按钮文字] = 点击显示的描述 }`（消费端 `screen_map.lua:7002-7093`，缺条目走 default 占位 ⇒ 殿堂无介绍）。**写法必须照成熟插件（viper:735 / zezitra:662 同款）**：`package.loaded["strings.hero_room_special"]` 优先（不主动触发重模块加载，其顶层 require entity_db/all.constants）+ fallback `pcall(require)` + **`type(x)=="table"` 校验**（loaded 被其他返厂旧插件污染成 number 时只降级不崩——gerald/zezitra 没防 number 实测崩）+ 执行时机放 **E.load 钩子**（entity_db 加载上下文），**别在 hook:init 主动 require**。
3. **入口文件必须 `return hook` 结尾**（+ 对齐其他插件的 `hook:unload`）：否则 `plugin/plugin_main.lua:72` 只 `log.error("Must return table")` **静默跳过**——不弹窗、零反馈。判据：AppData 侧 `config.lua` 无 `last_used_at` ⇒ 游戏从未加载它。语法校验查不出（nil return 合法）。
4. **跨关资源 + 特效家族**：`STAGE_EXOSKELETONS` 要覆盖技能特效/贴花的 Def 前缀（`hit_fx`/`hit_decal` 指向的 fx/decal 模板是全局的、实体能创建，但其 **exo 只在原关卡加载** ⇒ 报错 `animation X_run not found` 的 X 即缺的 exo 名；按 Def 名 grep `kr1/heroes.lua` 找家族全貌，备用档 `_1Def` 一并带上）。HOOK `director.load_texture_groups`（`item_name=="game"`）/`load_sound_groups` + `EXO:queue_load` + `exos_count=999999` 防卸载。
5. **缺资源守卫**：引擎按 `hero_data` 拼 `go_<名>` 加载，不存在 ⇒ `preload_atlas_from_bytecode` 返回空表 + 音效组空组兜底（抄 `hero_viper.prevent_missing_resource_errors`）。
6. **立绘/缩略图**：优先复用同形象可选英雄的 KR1 帧号（thumb/icon/portrait 同号），**零自有 UI 图注册**；不要写 `from_kr`。
7. **信息条/文案键自带**：`HERO_<X>_NAME/SPECIAL/DESCRIPTION` 写 `i18n.msgs[locale]`（插件的 `locales/*.lua` 是死文件）。

## 经验系统三件套（舞台模板全无，可选化必补）

1. **经验来源**：攻击/弹丸挂 `xp_gain_factor`（damage 绑定：`health.lua:627-634` 按 `damage_applied × factor` 喂 source 英雄，不需要 `hero.skills` 表）。⚠ `xp_from_skill` 只在引擎技能结算路径生效——本体脚本**手动 `create_entity` 发弹丸**的技能（如 `y_bombardement`）用不了，必须走弹丸系数。系数参照 KR1 原版档：普攻 1.6~4.8、二招 3.6~5、远程弹 2.4~2.9。
2. **升级结算**：外层循环每帧 `SU.hero_level_up(store, this)`（可选英雄的 update 才有这段，舞台 update 没有 ⇒ 经验只进 `xp_queued` 永不结算）。
3. **升级回调**：`hero.fn_level_up` 必须给（`script_utils.lua:1047` 升级时调用，缺了**升级瞬间必崩**）。⚠ KR1 满级开局 = `level_utils.lua:408` **for i=1..10 循环调 fn_level_up**——fn 里做的事必须幂等、按 `hero.level` 全量写。

## update 包装 = 外层协程（⭐ 核心结构）

- 引擎对 update 协程**只 `coroutine.create` 一次**、每帧 resume 同一个（`main_script.lua:93-100`）；本体 update 是 `while true` 永不返回 ⇒ **薄包装转调后 wrapper 代码只在协程首帧跑到转调行为止**——"每帧覆写"全是幻觉（首帧写一次字段留实例上，看似生效）。
- 正确结构：
  ```lua
  local function warlord_update(this, store)
      apply_tiers(this, store)                     -- 首帧：配档 + 兜底 fn_level_up
      local co = coroutine.create(本体.update)
      while true do
          SU.hero_level_up(store, this)            -- 每帧：结算经验/升级（fn_level_up 内刷档）
          if this.hero.level ~= applied_level then -- 等级变化检测（兜存档恢复/满级循环晚于首帧）
              applied_level = this.hero.level
              apply_tiers(this, store)
          end
          -- 未解锁技能锁定：每帧顶 ts（见下）
          local ok, err = coroutine.resume(co, this, store)
          if not ok then error(err, 0) end         -- 透传错误给 main_script.lua:102
          if coroutine.status(co) == "dead" then return end
          coroutine.yield()
      end
  end
  ```

## 必背坑

- **AC/CC 组件装配吞"组件表内新字段"**：`timed_attacks.list[1].<新键>`（如 min_spread）模板层补**无效**（游戏内仍 nil），必须**实例层**写；模板**顶层散字段**（`controable`、`fn_level_up`、`xp_gain_factor` 挂 attack 上——在组件 schema 里的）走 quickcopy/装配透传，模板层可设。分不清就全走实例层。
- **`SU.delay_attack`（`script_utils.lua:487`）在舞台 update 里是协程首帧跑一次**（46064/46068 在 while 循环外），之后 `ts` 无人维护 ⇒ 锁技能（未解锁不发动）= 外层循环**每帧顶 `ts = tick_ts - attack.cooldown + 0.1`**（"CD 只剩 0.1 秒"）：施法检查（`tick-ts <= cooldown`，45793/45881）恒真 ⇒ 永不发动；且 `time_since_cast ≈ cooldown`（20/15）远大于 fts(1)=0.033 的动画阈值 ⇒ **第三方插件（hero_auto_rally 等）的「技能动画中不移动」判断（`now - ts < hit_time + fts(1)`）不会误判**。⚠ 顶 `ts = tick_ts` 会让 time_since_cast≈0 恒小于阈值 ⇒ 英雄被判"永远在放技能" ⇒ **自动调集失效**（2026-10-15 实测）；⚠ 顶 `cooldown = 1e9` 会被信息条当 CD 显示成「100000000」。
- **护甲**：走 `health.raw_armor = X` + `SU.update_armor(this)`——`health.armor` 是含 buff 的计算字段，直写会被覆盖。
- **升级回满血**（`update_hp` 口径）：Dove 无 `U.heal` ⇒ `h.hp = km.clamp(0, h.hp_max, h.hp_max)`；回血口径 = **max 血 × `GS.soldier_regen_factor`(0.2)**（KR1 可选英雄），不是固定值。
- **召唤物手动调集 = 原版标记 `controable = true`**（模板顶层散字段，杰拉德圣骑士 `soldier_gerald_paladin` 范式）：兵经 `last_hook.lua:14-16` 自动进 `store.soldiers`，玩家 **F 键**（`patches/keyset_default.lua:20` `reinforce="f"`）框选 → 点地图 → `GUI_MODE_RALLY_CONTROABLES` 原生环形落位（`game_gui.lua:7636`）。E 键 = `controable_other` 组。零自研 UI。
- **召唤档位切换**：改 `timed_attacks.list[2].entity` 模板名即可（召唤脚本按 `dg.entity` 名 `create_entity`）；`initial_entity` 只在舞台开场路径消费（玩家局 `initial_squads_pos` 为空）。多档 = 注册多个深拷贝副本按等级换名。
- **召唤物伤害不喂英雄经验**：source 是卫兵自身（`health.lua:628` 按 source 找英雄），与原版召唤物一致。
- **必补 `vis.flags |= F_HERO`**：KR1 通用 hero 基类自带 `bor(F_HERO, F_FRIEND)`（`all/templates.lua:956`），而 **stage_hero 基类没有**、且舞台模板显式覆盖 `vis.flags = bor(F_BLOCK, F_FRIEND)`（heroes.lua:23330）⇒ 派生后 F_HERO 缺失，光环排除/敌人技能排除（vis_bans F_HERO）等不再把该单位当英雄。修复 = register 后 `tt.vis.flags = bor(tt.vis.flags or 0, F_HERO)`（增量 bor；先例 `soldier_veznan_demon`，heroes.lua:7330）。另注意：`hero_stats_enhanced` 等**按模板名硬编码名单**识别英雄的第三方插件，新英雄要单独找作者/自己加名单。
- **插件 dev 目录位置注意**：`compare_plugin_sync.py` 默认 dev = `<root>/KingdomRushDove/mods/local/`；若源放在 `<root>/mods/local/` 必须显式 `--dev`。
