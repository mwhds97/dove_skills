---
name: iron-marines-hero-port
description: 把 Iron Marines 英雄完整移植进《王国保卫战 Dove 版》的全链路流程：资源挖掘（UnityPy 读 bundle/PPtr 反查/MonoScript 类名）、C# 行为脚本反编译（ilspycmd 免 SDK 跑法）、Dove 侧插件范式（director 守卫/动画键规则/半紧画布/双连发/伤害单源）。另含**英雄移植通用的两条硬知识**：①**mod 是否叠加**（`mod_lifecycle:on_insert` 判据链；⚠ `modifier.resets_same` 组件默认 **true** ⇒ 普通 mod **默认唯一、不叠加**，反复 `queue_insert` 只会刷新计时；**DPS = 单次伤害 ÷ damage_every**；想真叠层必须显式 `max_duplicates`。曾误判成「×N 杠杆」，已纠正；另附 `mod_hps.insert` 满血 return false）与技能经验入账（`SU.hero_gain_xp_from_skill` 引擎永不自动调，须显式调用；`xp_gain` vs `xp_gain_factor` 是两字段）；②**英雄 UI 图三条互不兼容路线**（A 借用本体帧 / B 自建真图集 `size==f_quad+trim` / C `I:add_image` 只画整张 PNG 须全画布）、四类槽位规格、`tt.info.portrait` vs `hero_portrait` 区分、槽位撞号查全库、`hero_room` 号段表 —— 完整规格见 `references/hero-ui-images.md`。触发词：移植英雄、Iron Marines 英雄、HeroMarine、HeroTrabuco、钢铁队长、自由猎人、反编译 Unity、UnityPy dump、英雄 UI 图、殿堂缩略图、地图英雄按钮、HUD 英雄头像、英雄 slot 撞号、英雄技能 DPS、aura 持续伤害、mod 叠加。
agent_created: true
---

# Iron Marines 英雄 → 王国保卫战Dove版 移植全流程

成功案例：钢铁队长（HeroMarine/TAGGINS，插件 `iron_marines_port`）、自由猎人（HeroTrabuco，分析完毕见计划文档）。
游戏源：`E:\360downloads\GAME\Iron Marines`（Unity，Windows 版；路径随机器不同，装在哪就指哪）。

## A. 资源挖掘（UnityPy）

环境：`python`（任一 3.8+ 均可，UnityPy 已装；本机 managed venv 在 `%USERPROFILE%\.workbuddy\binaries\python\envs\default\Scripts\python.exe`）。

1. **本地化文案**：`ironmarines_Data/resources.assets` 内嵌明文，直接按关键词（英雄中文名/内部名）抽键值 → `<hero>_localization.json`。另含 `HeroesProgressionSettings`（全英雄成长 JSON，已提取 `.workbuddy/heroes_progression_settings.json`，数值参考用）。
2. **prefab 组件**：`ironmarines_Data/StreamingAssets/Windows/ingameassets` bundle（997MB）。先按名字搜 GameObject（含弹丸/特效/控制器全套，搜 `<内部名>` 小写子串）。
3. ⚠ **组件遍历别用 `cpt.component`**（PPtr 无此属性）——先建 `{obj.path_id: obj}` 索引，再按 `m_Components` 里 PPtr 的 `m_PathID` 反查，然后 `read_typetree()`。参考 `.workbuddy/extract_trabuco_2.py`。
4. ⚠ **MonoBehaviour 识别类名**：组件 typetree 里只有 `m_Script` PPtr，要先用 bundle 里的 MonoScript 对象建 `{path_id: m_ClassName}` 表反查。类名通常 = 行为语义（HealthBehaviour / MovementBehaviour / `<Hero>RangeAttackBehaviour`…）。
5. **数值位置经验**：HP/移速/回血/视觉范围/冷却在 prefab 组件顶层；伤害/成长**不在 prefab**（Damage 字段全是 0，来自游戏 Configuration 资产）→ 伤害直接自定，别挖。
6. 图集三件：`TextAsset <Hero>-hd`（描述）+ `Texture2D <Hero>-hd`（图）+ sd 版。帧名/帧数可从 TextAsset 正则抽。

## B. 行为脚本反编译（ilspycmd 免 SDK）

1. 本机只有 .NET 运行时无 SDK → 不能 `dotnet tool install`。**nuget 拉 nupkg 解包直接跑**：
   ```
   curl -sL https://www.nuget.org/api/v2/package/ilspycmd/8.2.0.7535 -o ilspy.nupkg
   unzip → pkg/tools/net6.0/any/ilspycmd.dll
   "C:/Program Files/dotnet/dotnet.exe" <path>/ilspycmd.dll <dll路径> -t <类名> > out.cs
   ```
2. 游戏逻辑在 `ironmarines_Data/Managed/Assembly-CSharp.dll`（个别类带 `IronMarines` 命名空间，`-t` 要写全名）。先 `-l c` 列类 grep 找齐。
3. 常配对读取：`<Hero>TransformationBehaviour`（形态切换）、`<Hero>*RangeAttackBehaviour`（普攻）、`<Hero>ResilienceScript`/致死被动、`<Hero>EatEtherium` 类特技、`AreaEffectDamage`（DoT 圈）、`BaseRayScript`（hitscan 射线：距离/150 拉伸+角度旋转+0.01s 判定）、modifier 基类族。
4. 产出存 `.workbuddy/decompiled/<类名>.cs`。

## C. Dove 侧移植范式（iron_marines_port 已验证）

- **交付物要带 `README.md`**（`mods/local/` 下所有官方插件都有：`boss_crocs_hero/readme.md` 等）。结构照抄这个套路：功能简介 → 主要特性 → 使用方法 → 游戏内配置（含**生效时机表**：模板数值需重启 / 运行时读表的下一张图生效）→ 基础属性表 → 1-10 级成长表 → 各套攻击表 → 技能详解表（按技能等级列 1/2/3）→ 特殊机制（骑马等）→ 数值三档划分 + 写死清单 → 与**重制版原值差异一览表** → 已知问题。写之前先读反编译数据摘要拿原版值做对照（`.workbuddy/deadeye_decompiled/Johnny_Deadeye_数据摘要.md`），并区分「原版就有」与「移植时原创」的机制（Johnny 的「瞄准靶心」就是原创，原版 SPECIAL 只有两项）。
- **护甲减伤换算**（`all/utils.lua U.calc_protection`，写文档/算数值必查）：物理 → `armor - reduce_armor`；**枪击 `DAMAGE_SHOT` → ×0.7**；电击 ×0.5；**爆炸 `DAMAGE_EXPLOSION` → `armor*(0.2*armor+0.4)`**（0.28 只剩 12.8% 减免，比物理弱得多）；突刺 `calc_stab_protection`；真实伤害 → `protection = 0`。单发伤害 = `U.frandom(damage_min, damage_max)`（`all/script_utils.lua:609`）→ 区间是**每次随机**，不是固定值。
- ⭐⭐ **改伤害类型前必查「免疫清单」—— 爆炸伤有隐藏盲区**（2026-10-01 实测）：
  `DAMAGE_PHYSICAL_GROUP`（`all/constants.lua:108-146`）**包含 `DAMAGE_EXPLOSION`**
  ⇒ `immune_to = DAMAGE_PHYSICAL_GROUP` 的敌人**同时免疫物理与爆炸**。
  `kr1/enemies.lua` 里有 4 个这类灵体：`enemy_spectral_knight`(2110) / `enemy_lycan_werewolf_phantom`(2431) /
  `enemy_ghost`(4618) / `enemy_phantom_warrior`(4687)；另有 1 个 `immune_to = DAMAGE_EXPLOSION`、
  1 个 `immune_to = DAMAGE_ALL_TYPES`（`enemy_twilight_scourger_banshee` 5585）。
  ⇒ 把「真伤弹丸」改成「爆炸弹丸」会**换来对高甲的穿透力，同时丢掉对灵体类的伤害**，
  这个副作用必须写进 README 并让用户知情。反过来：**真伤（`DAMAGE_TRUE`）不吃任何免疫**。
- ⭐ **删模板字段时必须连「注入行」一起删**：`hero_templates.lua` 里形如
  `tt.hero.skills.xxx.field = B.skills.xxx.field` 的注入行**不会随源键删除而消失**，
  源键没了它就静默注入 `nil`（**全程不报错**）⇒ 排查时要 **grep 源键名时一并命中注入行**，
  不只是找 `balance.lua` 里的定义。
- **插件结构**：`KingdomRushDove/mods/local/<plugin>/`，入口 `<plugin>.lua` + `scripts/hero_templates.lua` + `hero_scripts.lua` + `_assets/images/<图集>.lua`。游戏读 `%APPDATA%/LOVE/kingdom_rush_dove/plugins`，改完要同步。⚠ **别用 `diff -rq` 判同步**：本机 Git Bash 对中文路径会漏报（实测只报 1 项、实际 3 项差异）→ 用 `.workbuddy/compare_plugin_sync.py <插件名>`（逐文件 MD5，默认只读报告；`--push <文件…>` 才推），它同时挡住「AppData 侧是用户手工调参、被整目录覆盖」的风险。数值集中放 `scripts/balance.lua`；要做「游戏内可改数值」（`<plugin>_config.lua` + `on_config_change` + 逐键映射验证探针）见技能包 **`kr-dove-plugin-config`**。
- **改完别只靠肉眼 + 进游戏试**：用 `lua51.dll` 能在不开游戏的情况下加载真 `entity_db` 对模板/科技/幂等做断言，见技能包 **`kr-dove-offline-lua-harness`**。
- **想让英雄吃箭塔科技**：只有 `archer_precision`（暴击）是天生就吃的；其余弹丸效果类（破甲/黑曜石/撕裂/附魔/对空/放血）必须把弹丸模板名插进 `upgrades.arrows` 白名单，并处理"同关 patch 两次会叠加"的幂等（做法见 `johnny_deadeye` 的 `scripts/arrow_tech.lua` 与本项目 MEMORY.md）。
  - ⭐ **"插件往白名单加名"和"原版本来就在名单里"是完全同一个机制**（2026-10-01 用户追问核实）：`upgrades.arrows`（`kr1/upgrades.lua:1173`）是一张**静态字面量表**，全库 grep 确认**引擎运行期从不写它** —— 原版英雄（`arrow_hero_alleria` / `bullet_asra` / `knife_catha` …）就是**写死在表里的字符串**。`patch_templates` 用 `pairs(self.arrows)` 遍历，**不区分来源**。⇒ 插件运行期 append 同一张表即可，写法 `arrows[#arrows+1] = name`，或别家 mod 用的 `table.arrayensure(UP.arrows, name)`（`iron_tower` / `weird_archer` / `Demon_Sentinel` / `TrollAxeThrower` 都是这一行）。唯一要自己补的是**幂等**与**悬空名保护**（`patch_templates` 里 `T(n).bullet` 直接索引，名字在册而模板不存在会当场崩）。
- ⭐ **别再以为"本体（Dove 原版）远程英雄就吃箭塔科技"—— 2026-10-01 实测证伪**。用 `.workbuddy/probe_dove_hero_arrow_tech.lua`（离线起真引擎，见该文件头注释）跑出的事实：
  - **本体英雄弹丸 138 个，只有 8 个在 `upgrades.arrows` 白名单里**（= 5 位英雄：`hero_alleria`(1)、`hero_asra`(2)、`hero_catha`(1)、`hero_elves_archer`(1)、`hero_vesper`(2)）；跑完 `UP:patch_templates()` 后**也只有这 8 个**被改（破甲 + 黑曜石 + 撕裂/附魔/放血）。
  - 判"有没有被改"必须**patch 前后快照对比**（`reduce_armor` / `#damage_hooks` / `#mods`）—— 直接判 `bd.damage_hooks ~= nil` 会**假阳性 125/138**，因为 `damage_hooks`/`mods` 是基模板默认就有的空表。
  - 天生就吃的只有暴击：`archer_precision` 在**基弹丸脚本** `scripts.shotgun.update`（`all/scripts.lua:3974`）里判定 → 但**本体 138 个英雄弹丸里只有 6 个继承它**（`shotgun_bolin`×2、`pirate_shotgun`、`van_helsing_shotgun`×2、`van_helsing_silverbullet`），其余英雄弹丸都覆写了 `main_script.update`。⇒ "继承基脚本"才是吃暴击的判据，不是"是英雄"。
  - 英雄脚本里运行时读的科技只有 `heroes_lethal_focus` / `mage_spell_of_penetration` / `engineer_efficiency`，与箭塔弹丸效果无关。
  - 对照：重制版（KR1）更严 —— `upgrades.decompiled.lua` 的 `patch_templates` 各升级项都是**内联静态名单**，`archer_piercing` 只覆盖 `arrow_1/2/3`、`arrow_ranger`、`shotgun_musketeer*` 等塔弹丸，**一个英雄弹丸都没有**；暴击判定在**塔**的脚本里（不在弹丸脚本）。重制版里唯一把英雄列进名单的是**兵营**科技 `barrack_barbed_armor` 的 `health.spiked_armor`（含 `hero_deadeye`）。

- **director 守卫**（必须）：玩家选中英雄进关时 `director.lua:558` 强制加载 `go_<英雄名>` 图组+同名音效组 → `prevent_missing_resource_errors()`：① `image_db.atlas_uses` 元表 __index 拦截返回 1；② 劫持 `preload_atlas_from_bytecode` 命中名返回 `{}`；③ `sound_db.groups[名]={sounds={}}`。挂 hook:init + hook.E.load，flag 防重装（参照 boss_crocs_hero）。
- **注册链路**：`E.load` 后 `RT("<hero>","hero")` + `AC(tt,"melee","ranged")`；`I:load_atlas(1, ...)`；`A:register_animations`；`map_data.hero_data` 注入 + `hero_names_config` 着色 + `strings.hero_room_special` + i18n load_locale 钩子重注入名字。
- **局内英雄头像尺寸**（HUD 左下 `HeroPortrait`，`all-desktop/game_gui.lua:2071-2145`）：按钮 **102×101**；原版帧 `hero_portraits_*` = 设计 **144×142** / trim **28,22** / 纹理 87×87（gui_portraits 图集，归 **game_gui** 场景加载 → 显示 102.4×101.0 正好铺满）。自定义头像走 `info.hero_portrait` + `I:add_image(name, img, group, scale)`。
  - ⭐ **`I:add_image` 的 `scale` 参数就是 `ss.ref_scale`，语义是「图集渲染比例」，不是"随便挑个缩放倍数"**：引擎按 `场景.ref_res / TEXTURE_SIZE_ALIAS[贴图组目录名]` 给整组帧打比例（`director:get_texture_scale`，`all/director.lua:159`）。`screen_map`/`slots`/`loading`：ref_res = `fullhd` = 1080、贴图组也 fullhd → **1**；**`game_gui` 的 ref_res = `TEXTURE_SIZE_ALIAS.ipad` = 768**（`all-desktop/game_gui.lua:105`）→ **768/1080 ≈ 0.71111**。
  - ⇒ **正确姿势（2026-10-01 定案，推翻了此前「源图裁成内容尺寸 + trim={28,22}」的写法）**：
    **`I:add_image`（`image_db.lua:726-743`）忽略调用方给的一切布局数据**，只按 PNG 实际尺寸建 quad ——
    `quad = G.newQuad(0, 0, w, h, w, h)`（w,h = **PNG 实际尺寸**）、`trim = {0,0}`、`size = {w,h}`；
    绘制 `kui.lua:671` `G.draw(image, quad, trim[1]*ref_scale, trim[2]*ref_scale, 0, ref_scale)`
    ⇒ **画的永远是整张 PNG，`trim` 只当整体位移**。插件事后覆写 `ss.trim`/`ss.size` 只改元数据、**改不了 quad**。
    ⇒ 插件 PNG 必须是「**原版整幅画布 + 内容留在原版 bbox 位置**」，`trim` 恒 `{0,0}`，偏移靠 PNG 自身留白表达。
    - ❌ 给内容区紧裁（87×87）+ `trim={28,22}` ⇒ 整张被移到 (28,22) ⇒ **跑出相框**（实测 ember 地图按钮头溢出即此）
    - ✅ 给 144×142 全画布（内容 87×87 @ (28,22)）+ `trim={0,0}` ⇒ 正确
    - 生成：`内容 = img.crop(img.getbbox())` → `canvas = RGBA(画布尺寸)` → `canvas.alpha_composite(内容, (ox,oy))`，`(ox,oy)` 用**原版源图实测 bbox**。
  - ⭐⭐ **四类槽位权威规格**（`trim` 一律 `{0,0}`）：
    | 家族 | 原版整幅画布 | 内容 @ bbox | 用途 |
    |---|---|---|---|
    | `mapButtons_portrait_hero_*` | 226×184 | 72×68 @ (78,46) | 关卡地图英雄按钮（`screen_map.lua:992`） |
    | `hero_room_thumbs_*` | 84×84 | 60×63 @ (12,11) | 殿堂/关卡选择缩略图（`:6586`） |
    | `portrait_notxt_*` | 274×386 | ~254×371 @ (10,8) | 殿堂大立绘 |
    | `hero_portraits_*` | 144×142 | 87×87 @ (28,22) | 战斗 HUD 槽 = 本体「一键召唤」按钮源（`game_gui.lua:2079`） |
  - ⭐⭐⭐ **`I:add_image` 不是唯一路线 —— 三条互不兼容的路线，先选路线再动手**：
    | 路线 | 做法 | 适合 |
    |---|---|---|
    | **A 借用本体帧** | `hero_data` 写 `thumb=N, icon=N, portrait=N, from_kr=K`，命中本体 `krK_*_%04i` 真帧；运行时只用 `view.image_offset = vec(ox,oy)` 微调（⚠ 是 KView 绘制偏移字段，**不是** trim） | **本体图集已有该英雄整套 UI 帧**（`Ten_Plagues_Isfet`：`16/16/16, from_kr=4` → `kr4_*_0016`，零自制贴图） |
    | **B 自建真图集** ★推荐 | `_assets/images/` 放 `.lua`(帧表)+`.dds`(贴图)，`I:load_atlas(ref_scale, path, name)` 加载；帧写**真 `f_quad`**：`["Alric_Avatar_2"]={size={226,184},trim={78,46,76,70},f_quad={256,173,72,68}}` —— ⭐ **`size == f_quad + trim` 硬约束**（72+78+76=226 ✓），`trim` **有意义且必须**。微调 `adj()`：`f.ref_scale=base*smul; f.trim[i]=base+o/ref_scale`（存 `_alric_ui_base` 快照保幂等） | **自制英雄 + 要精确构图**（`Alric_Overhaul`，另有 `alric_asset_hooks.lua` HOOK `I.load_atlas/queue_load_atlas/preload_atlas*` 做路径重写） |
    | **C `I:add_image`** | 见上：整张 PNG + `trim={0,0}` + 全画布留白 | 自制英雄 + 只有现成 PNG 且构图已合适 |
    ⚠⚠ **「trim 恒应为 {0,0}」只在路线 C 成立**，别推广到路线 B。
  - 代码里别硬编码 0.7111：写 `scene_texture_scale(scene_name)`，每个 `UI_IMAGES` 项标 `scene = "game_gui" | "screen_map"`。
    - ⚠ **不许 `require(scene_name)` 去读 `scene.ref_res`**：插件在 **`hook:init`** 就会调本函数，而 `screen_map` 这类大屏幕文件此刻可能还没被引擎 require —— 一句 require 会让它整个提前执行（副作用 + 白跑）。改用**静态映射**，数值照抄各场景文件：`{ game="ipad"（`all/game.lua:66`）, game_gui="ipad"（`game_gui.lua:105`）, screen_map/screen_slots/screen_loading="fullhd" }`，再 `ref_res / TEXTURE_SIZE_ALIAS[director.params.texture_size]`；`TEXTURE_SIZE_ALIAS` 由 `main.lua:3 require("all.constants")` 保证早于插件 init 已是全局。`get_texture_scale` 的首参 = **scene 名**（`director.lua:429` 的 `name`；`plugin_utils.load_texture_groups` 注释明写 "item_name: scene 名称"）。
  - 断言脚本 `.workbuddy/verify_deadeye_hud_portrait_scale.lua`：**原样抽取** `SCENE_REF_RES_ALIAS` + 该函数加载（不复制粘贴，防走样）+ 用真 `gui_portraits.luac` 的 `hero_portraits_0002`（标准帧 87×87/trim 28,22，**别用 `hero_portraits_0001`**，它是 84×85/trim 31,24 的异类）做几何对照。脚本**故意不 preload 场景模块** → 若函数里残留 require 就会真去加载 `screen_map.lua` 而失败，等于给上面这条隐患装了回归测试；另有一条「函数体内无 `require`」的结构断言。
  - ⚠ 旧版本这里曾写「显示尺寸 = 源尺寸×s，挑 s≈0.4 让 256→102.4」——**那只是把尺寸蒙对、位置仍错**：`trim` 是「纹理在视图内的摆放偏移」，会跟着 `ref_scale` 一起缩放（`lib/klove/kui.lua:668`），漏掉它内容就贴到视图左上角。别再用"调倍数"的心智模型。
  - 伴生元素：等级数字 16×16@(66,65)、冷却遮罩 63×63、血/级条 `hero_portrait_bars_0001/0002`@(23,83)、相框 `heroPortrait_0001`（size 144×142 / trim 5,3）；minified UI 模式下 portrait 另 ×1.05（`set_anchor_to_center` + 居中 + 缩放，故两种模式都能对）。
  - ⚠ 反例：`InfoBar` 的左下信息栏头像（`info.portrait`）是**自适应绘制**（`game_gui.lua:2807` 只按 quad 尺寸 + 相框圆心缩放裁剪，不看 `size`/`trim`/`ref_scale`）→ 那张图**不需要**布局元数据，别照抄上面的规格。
  - ⚠ 排查姿势：UI 图"大小不对"先算 `原版设计尺寸 × 场景 ref_scale`，和你 `I:add_image` 实际打上去的 `ref_scale` 比；`scale=1` 打在全组 0.7111 的图集上，任何图都会大 1.406 倍。别只看图大小、忽略 `trim` 造成的位移。
- ⭐**殿堂「四条点数」的数组顺序 = 生命 / 伤害(攻击) / 射程 / 速度**（不是 attack 优先！）。`hero_data` 条目 `stats = {生命, 伤害, 射程, 速度}` —— **按语义名对号入座**，别按"想到的顺序"写（johnny_deadeye 定值 `{ 3, 7, 8, 6 }` = 生命3/伤害7/射程8/速度6）。依据 = `hero_room_view` 的 `hero_room_stats.children` 顺序（`hero_room_stat_health`→`stat_damage`→`stat_range`→`stat_speed`），`screen_map.lua` 按 children 下标逐格 `c:set(hd.stats[i], true)`。写反了**不报错**，且 Dove 的殿堂里**没有行标签/图标**（`HeroStatDots` 只画点，`heroroom_bg` 里也没图标）→ 肉眼看不出顺序，只能靠代码/交叉断言确认。另：模板 `hero.fixed_stat_*` 在 Dove 引擎里**无人消费**，别以为改它就生效。
- **动画键（⭐⭐ 两侧必须逐字命中，2026-10-01 实证）**：`prefix` 不带尾下划线（引擎拼 `prefix_.._%04i`）；模板 `sprite.name` 只写后缀（动画键 = prefix_name，写全名会双拼）。注册放 A:load 首跑后（双钩子幂等）。
  - 完整链条：**运行时键** = `sprites[1].prefix .. "_" .. sprites[1].name`（`all/systems/render.lua:345`），其中 `name` 会被 `size_names[unit.size]` 替换（`all/script_utils.lua:1134` 等）；**注册侧** = `animation_db:register_animations`（`animation_db.lua:84-88`）按**字典 key** 取，帧名用 `a.prefix .. "_%04i"`（`:27`）。
  - ⇒ 两条铁律：**① 注册 key == 模板 `prefix .. "_" .. size_names[size]`；② 注册项里的 `prefix` == 图集帧名前缀。**
  - ⚠⚠ **照抄原版模板不一定对**：原版 `mod_viper_poison` 写 `prefix="viper"` 是因为**原版图集**帧名是 `viper_%04i`；我们自制/重打包的图集帧名是 `viper_poison_%04i` ⇒ `prefix` 必须写 `"viper_poison"`，且 `size_names` 要给名字（`{"small","medium","large"}` + `name="small"` ⇒ 键 `viper_poison_small`）而不是原版的 `{"poison"×3}`。**先 `grep` 图集实际帧名，再定 prefix 与 key。**
  - ⚠ 报错形态：`animation_db.error fn() - animation X not found` **紧跟** `image_db.error s() - Sprite nil was not found in the atlas db.` —— **两条同源**（key 查不到 → 传给 image_db 的是 nil），**不要当两个 bug 分别查**。
  - 守门：`.workbuddy/verify_viper_anim_and_info.lua`（解析图集帧名 ↔ ANIM_DEFS 双向命中 + 反例断言「裸前缀 `viper` 不得存在于图集」）。
- ⭐⭐ **英雄信息面板空白 = `tt.info.fn` 抄错了代**（2026-10-01 实证）：消费点 `all-desktop/game_gui.lua:3088 InfoBar:update_stats`（**有判空，取到 nil 时不崩，只是全空**）。
  - **Dove 的 `scripts.hero_basic` 只有 `get_info`**（`all/scripts.lua:1458-1460`，= `soldier_barrack.get_info`）；默认值见 `all/templates.lua:959 hero.info.fn = scripts.hero_basic.get_info`。
  - ⚠ **KR1 的 `get_info_melee` / `get_info_ranged` / `get_info_ranged_with_damage_factor[_and_magic_armor]` 在 Dove 里全不存在** ⇒ 照抄原版 = nil = 面板全空。判据：`grep -rn "get_info_melee" --include=*.lua all/ kr1/` 零命中（注意 `mods/local/资源/output/` 有**整份引擎源码备份但不被加载**，别被它骗了）。
  - 取数链（`all/scripts.lua:520-645`）：melee = `attacks[i].damage_min/max` × `damage_factor`；ranged = `E:get_template(a.bullet).bullet.damage_min/max`（`:548-574`）；无 ranged 且多近战招 → 回退第 2 招（`:606-625`）；`no_ranged` 决定面板是否隐藏远程栏。
  - 📌 **`hero_basic.get_info` 足够用**（也能报两段伤害），**不必**像 `johnny_deadeye` 那样自定义 `get_info`；只有要报 `damage_icon`/`immune_*` 等特殊字段时才自定义。
- **渲染原点 = 半紧画布**：`size={画布宽,f_quad高}`、`trim={原画布左距,0}`、`anchor=v(0.5,0)`。横向保留画布对位（pose 摆动不丢），纵向脚底钉 pos.y。纯紧画布会普攻左右横跳。trim 四元组={左,上,右,下}。脚本 `.workbuddy/semifit_hero_marine_canvas.py`。
- **旋转帧转正**：tk2d 旋转帧逆时针 ROTATE_90（用成功帧像素级标定过）。空帧量化 `.workbuddy/check_atlas_blank_frames.py`。
- **hp 初始化口径**：模板 health 只有 hp_max；`level_up_basic` 只赋 hp_max；`level_up` 末尾 `update_hp`（nil→满血，否则 U.heal）；insert 不带 initial。乱写 apply_hp 会 `hp nil` 崩溃。
- **伤害单源化**：弹丸模板存真值；level_up 把近战 attacks[1] 的 damage 抄弹丸值；面板 get_info 读弹丸模板实时值。
  - ⭐ **`get_info` 的乘数链**（`all/scripts.lua:520-645`）：melee = `attacks[i].damage_min/max`，**再乘** `this.unit.damage_factor`（**再加** `this.unit.damage_buff`）；ranged = `E:get_template(a.bullet).bullet.damage_min/max`（`:548-574`，同样吃 buff/factor）。⇒ **面板跑离线桩时若 `unit.damage_factor` / `damage_buff` 是 nil → 算术直接崩**，假实体必须补 `unit = { damage_buff = 0, damage_factor = 1, cooldown_factor = 1 }`。
  - 「远程伤害/射程栏为空」= `ranged.attacks[i].bullet` 指向的弹丸模板**没有 `bullet.damage_min/max`** ⇒ `get_info` 的 ranged 段整段跳过（`:554` 的判据）。
- **连发**：原生 loopable 连发 = `attack.loops` + `animations={nil,"主动画"}` + `shoot_times={相对动画起点的开火时刻}`（FPS=30）；动画事件帧开火用 `AnimationEventTriggered` 思路（Dove 侧等价 shoot_times）。
- **多形态英雄**（自由猎人）：⚠ 重大修正——**Dove 原生支持多层同步动画，三层贴图不用合成**！`sprite.group` 字段（components.lua）+ `U.animation_start_group/animation_finished_group`（utils.lua:838）把同 group 的多个 sprite 按同一动画键名同步驱动（每 sprite 用自己的 prefix 拼帧名），塔的枪管层是活例（kr1/archer_towers.lua:1574、kr1:6938 `group="gun"` + `ranged.attacks[1].sprite_group`）。三层 = render.sprites[1..3]（layer1 身体/layer2 激光/layer3 霰弹）同 group="body"、同 anchor、各自注册 ANIM_SEGMENTS 同段动画键；切形态 = sprites[2]/[3].hidden 互斥 + ranged.attacks disabled 互斥。atk 侧 `attack.sprite_group` 让攻击动画走组播放。
- **clip 段边界有权威数据（2026-09-28 修正，别再 contact sheet 目测！）**：`resources.assets` 里按引用名（如 `Spritesheets/Animations/Army/army_hero_trabuco_animations`，在英雄配置 JSON 里能搜到路径）找到的**动画库是 XML TextAsset**（plist 风格）：每 clip = `<key>名</key><dict><key>prefix</key>…<key>fromIndex</key><integer>A</integer><key>toIndex</key><integer>B</integer><key>wrapMode</key>Once/Loop<key>triggers</key>（帧号→eventInfo: shot/action/sound）<key>layers</key>3`。fromIndex/toIndex 是 **1 基帧号**，layer1/2/3 同号平行对位（帧 N = layer{n}_00{N}）。工具：`.workbuddy/parse_trabuco_anim_lib.py`（输出 `trabuco_clips.json`/`trabuco_anim_lib.xml`）。C# 行为类里的 clip 名字符串（`hero_trabuco_Bullet_Shot_Side` 等）可先反查命名体系。⚠ 典型坑：自由猎人**没有 Bullet_Idle/Bullet_Run**——两形态共用 Energy_Idle(1-28)/Energy_Run(29-48) 身体动画，武器差异在 layer2/3 装备层。clip 无 fps 字段（tk2d 默认 30 fps 假设，Dove 侧 shoot_time=开火帧/30）。英雄无 levelup/respawn clip 时用 idle 段代。
- **clip 挖不到的兜底**（typetree 缺失时）：contact sheet 视觉分段 + 实测微调；268 帧级渲染脚本 `.workbuddy/render_trabuco_segments.py`（30 帧一块、带帧号条图，>2000px 宽会被压缩看不清，分块要小）。
- **用户转的图集描述自校验**：`(?<!a_)size` 正则（裸 `size` 会误配 `a_size`）；校验 trim 四元组与 f_quad 自洽（left+content_w+right=size.x）。
- **log 安全**：Dove 的 strformat 对 table 崩 → 一律 `.. tostring(x)`。
- **实体 AI = 永续协程**：英雄 main_script.update 必须是 `while true + coroutine.yield()` 主循环（marine/gerald 同构）；普通每帧函数 return 一次协程即死 → 不动/动画死/零报错。`goto label_loop` 收尾合法（游戏 lua51.dll 实为 **LuaJIT 2.1** 改名，goto 可用，lua_syntax_check.py 也放行）。
  - ⚠⚠ **`goto` 不能跳进 local 的作用域**（Lua 硬约束）：若在同一块里**先有 `goto label_x`、后有 `local y`**，会报 `<goto label_x> jumps into the scope of local 'y'`。
    实测（ember volcano 打断返还）：`goto label_364_0`（在前摇等待段抛错时跳走）之后我加了 `local interrupted` ⇒ 编译失败。
    **修法：把这个 local 声明提到所有 `goto` 之前**（哪怕它逻辑上后面才用），别改 goto。
- ⭐⭐ **改「冷却 / 计时」类逻辑时，方向必须用探针复算，别肉眼看公式**（2026-10-01 踩过）：
  技能可施放判据一般是 `store.tick_ts - a.ts > a.cooldown` ⇒ **要缩短冷却必须把 `a.ts` 前移（减）**。
  ember volcano「打断按比例返还冷却」我写成 `a.ts = start_ts + cooldown*ratio*refund`，
  结果**冷却反而变长**（纯函数探针算出"省下 -17.5 秒"＝多等 17.5 秒），改成 `-` 才对。
  ⇒ 凡涉及"提前 / 返还 / 缩短"，**先写一个纯函数探针打印正负号**（如 `.workbuddy/probe_ember_volcano_refund.lua`），
  通过后再回写引擎代码；光看公式极易把符号搞反且**不报错**。
- **手动发射弹丸字段清单**（对齐 script_utils.lua:1509-1536 标准发射器）：`b.pos:copy(枪口)`、`bullet.from:copy(b.pos)`、`bullet.to:set(target.pos + target.unit.hit_offset)`、`target_id`、`shot_index=1`、`loop_index=1`、`source_id`、`xp_dest_id`、`damage_factor=this.unit.damage_factor`。bomb 基类自带抛物线（bullet.flight_time）。
- 免死钩：`health.on_damage(e, store, d)` 返回 true 拦截（health.lua:655），配合 `h.ignore_damage` 做眩晕无敌。
- **⚠ 伴生实体（挂在别人身上的 modifier/aura）必须写组件字段**（2026-09-30 定案，johnny_deadeye 霰弹弹药架连踩四轮）：创建时写 `m.modifier.target_id` / `m.modifier.source_id`（aura 写 `aura.source_id`），**不是**顶层 `m.target_id`。引擎 `all/systems/mod_lifecycle.lua:15-20` 按组件字段查 `store.entities[modifier.target_id]`，nil 即 `return false` → `all/simulation.lua:250-253` **静默丢弃实体**（零日志零报错）。症状：实体永不出现、自己的 insert/update 永不执行、查找函数永远 miss。模板顶层同名标量引擎不消费，写错层 = 静默失败；回查 owner 也用 `store.entities[this.modifier.target_id]`。
- **静默丢弃/移除的排障姿势**（自证日志 + 微创探针）：① 插件内自建 `dbg()` 落 `love.filesystem.getSaveDirectory()`（ASCII 路径，io.open 无 936 编码问题；游戏日志只在控制台、事后不可查）；② 行为不变地包裹 `simulation.insert_entity`（调用后查 `store.entities[e.id]` 是否落地）、`queue_remove_entity` / `remove_entity`（`debug.getinfo(2,"Sl")` 记调用点 src:line）——谁拒的、谁删的当场现形；③ 插不进去先怀疑"组件字段没写全"，再怀疑 mod_lifecycle 的 bans / 同名 `resets_same` 分支。排障结束整段探针删掉。
- **新增自定义技能（非原版数据）**：① 数值进 `balance.lua` 一处（层数/上限/开关）；② 机制挂在弹丸生成点最省事——伤害写在弹丸实体上（`b.bullet.damage_min/max = 模板值 * 倍率`，**实体是模板的克隆，乘上去不会污染共享模板**）；③ 若做成"叠层"，用 `this._xxx = {target_id, stacks}` 存英雄实体上，换目标即清零，并区分"推进层数"（普攻每发）与"只读当前层数"（技能弹丸不推进）两个入口；④ 殿堂条目 = `strings.hero_room_special["hero_<名>"][技能中文名] = 描述`（消费端 `screen_map.lua:6996-7060` 用 `pairs` 生成按钮，**按键数自动增减，无图标依赖**、y=260/180/100…每项下移 80）；⑤ 英雄列表文案 `HERO_<名>_SPECIAL` 也要追加技能名（逗号分隔，同原生 `HERO_BIRD_SPECIAL`）。
  - ⭐⭐ **改「技能中文名」或「解锁等级」的完整落点清单**（2026-10-01 ember「克拉卡托」→「克拉卡托火山」实战）：
    **技能名**唯一来源 = `scripts/hero_room_texts.lua` **返回表的 key**。链路：
    `ember_hero.lua` `room_special["hero_<名>"] = room_texts` → 引擎 `all-desktop/screen_map.lua:6996`
    `pairs(special_map)` → `GGOptionsButton:new(name)` ⇒ **key 直接当殿堂技能按钮标题**，
    无外部对照表、改名不会失配。要改两处（是**两处独立文案**，别只改一处）：
    ① `hero_room_texts.lua` 的 key（殿堂按钮名）；② `localization.lua` 的 `HERO_<名>_SPECIAL`
    （英雄**列表页**的"技能一，技能二"并列串）。
    ⚠ `tt.info.i18n_key = "HERO_<名>"` **只是英雄级前缀**（名字/描述/SPECIAL），**不含技能名**，别改错。
    **解锁等级** = `balance.skills.<skill>.xp_level_steps`（稀疏表：key = 英雄等级 → val = 技能等级；
    两种写法等价：`{ nil,1,nil,nil,2 }` 位置数组 或 `{ [3]=1,[6]=2,[9]=3 }`）。
    ⚠⚠ 改它**必须同步校验脚本里硬编码的 `expect_<skill>` 等级数组**（如 `verify_ember_templates.lua`），
    否则报**假 FAIL**；改完 grep 旧等级确认无残留。

- ⭐ **殿堂技能描述里的数值必须"算"，不能写死字符串**（2026-10-01 用户要求「描述跟玩家配置走」时核实）：原生 `_assets/kr1-desktop/strings/hero_room_special.lua` 本身就是**算**的 —— `E:get_template(hero)` 取模板、`ss(key) = s[key][max_lvl]` 取**技能满级**值、`HERO_ROOM_FMT_*` 拼句，整表 `H[hero_name]` 在模块加载时构建。⇒ 插件若把描述写成字面量，配置一改就是**过期文案**（原生没有这个问题，别把它当"引擎行为"照抄）。做法（johnny_deadeye 的 `scripts/hero_room_texts.lua`）：从 `balance` 现算（技能数组取**最后一项** = 满级；运行时项直接读；templates 的 [固定] 项如弹药架容量则 `E:get_template("mod_shotgun_bullets").max_bullets`）；数字格式化照抄原生 `str()`（`%.2f` 去尾零，顺带吸收 `1.4-1` 浮点噪声）；倍率→百分比 `str((f-1)*100)`。⚠ 汉字数字表 `{"零","一",...}` 是 1-based，`CN_NUM[6]` 是"五" —— 要 `[0]="零"` 后直接索引，别写成 `v+1`/忘了偏移。构建点放 `hook.E.load`（与模板烤制同批，改配置同样要重启游戏）；**别在 `on_config_change` 里重建**（会显示新值而游戏仍跑旧烤值）。断言见 `.workbuddy/verify_deadeye_hero_room_texts.lua`（含"覆盖配置后文本跟着变"）。

- **殿堂「大立绘」（hero room 右侧大图）注入**（2026-09-30 johnny_deadeye 落地；此前一直是空白）：
  - 数据链：`HeroRoomViewKR1:new_from_table(kui_db:get_table("hero_room_view", ctx))`（`all-desktop/screen_map.lua:1076`）→ 模板 `kr1-desktop/data/kui_templates/hero_room_view.lua` 里 `id="hero_portraits"` 节点下，每个英雄一条 `{ id="portrait_"..hero, hidden=true, class="KView", children={ {class="KImageView", image_name=...}, {id="name_img", ...} }, pos=v(227,152), scale=v(0.77,0.76) }`。
  - 注入方式：`HOOK(kui_db, "get_table", fn)`，`name == "hero_room_view"` 时在返回表里找 `hero_portraits` 节点、插一条同构条目（记得**幂等守卫**：已存在 `portrait_hero_deadeye` 直接 return）。⚠ **位置不是随便的**：KUI 绘制顺序 = children **数组顺序**（`lib/klove/kui.lua:674 _draw_children` 是 `for i = 1, #self.children`，靠后的画在上层），而 `portrait_hero_name_label` 是 `hero_portraits.children` 的**最后一个** → `table.insert(children, entry)` 追加到末尾会把英雄名压在下面。正确姿势：先扫出 `c.id == "portrait_hero_name_label"` 的下标，`table.insert(children, insert_at or (#children + 1), entry)`。判"名字有没有被盖"别靠截图（名标签是 GUI 层 `HeroNameLabel`，目测永远在上层）——**比下标**。
  - 显隐由引擎控制：`HeroRoomViewKR1:show_hero`（`screen_map.lua:6756-6767`）里 `c.hidden = c.id ~= "portrait_" .. name`，且**强制把 name_img 隐藏**（本项目图集没有 `heroroom_bigportraits_name_*`）。⇒ 条目 id 必须严格等于 `"portrait_" .. hero_data[i].name`（即 `portrait_hero_xxx`）。
  - ⚠ 页面上的英雄名**不是**条目里的图，而是全局 `portrait_hero_name_label`（`HeroNameLabel:set_hero`）。所以"名字有显示"**不能**证明你的条目被插进去了 —— 立绘空白时先怀疑注入根本没跑。
  - ⚠⚠ **两个会静默吃掉整个功能的坑**：① `kui_db` 必须 `require("klove.kui_db")`（引擎侧 5 处都无 `lib.` 前缀）；写成 `lib.klove.kui_db` 会拿到**另一张表** → 钩子挂在引擎不看的表上（见技能 `kr-dove-tower-port` 的模块名一致性条目）。② 别 require `lib.klove.vector`（**不存在**，正确的是 `lib.klua.vector`）——`pcall(require, ...)` 失败只让 `ok_vector=false`，若随后有 `if not ok_vector then return end` 早退，注入就整体 no-op 且零报错。
  - ⭐⭐ **`screen_map` 的模块名陷阱（比上面两条更狠：会让游戏崩）** —— 2026-10-01 毒蛇实测：
    - 引擎加载它的模块名是 **`"screen_map"`**（`all/director.lua:405 _require("screen_map")`）；自定义 searcher（`main.lua:110-169`，搜索根含 `string.format("all-%s", KR_TARGET)` 即 `"all-desktop"`，且 `module_name:gsub("%.","/")`）让它落到 `all-desktop/screen_map.lua`，缓存键 `package.loaded["screen_map"]`。
    - **绝不能写 `require("all-desktop.screen_map")`** —— 那是**另一个缓存键**（搜索根 `""` 也命中同一文件）⇒ **文件被 `require` 两次**。而 `screen_map.lua:51` 是 `screen_map = {}`（**全局赋值、没有 `local`**）⇒ 第二次执行把**全局 `screen_map` 换成一张新空表**，而 `director` 手里仍是旧表。
    - 后果：`init_coro` 往旧表写 `unlock_data`，`MapView:initialize`（`:2059`）从**全局（新空表）**读 ⇒ `attempt to index field 'unlock_data' (a nil value)` → **一进地图界面就崩**（堆栈落在 2000+ 行外，离病因极远）。
    - **修法 = 惰性挂钩**：`HOOK(director, "queue_load_item_named", ...)`，在 `next(...)` 返回且 `name == "map"` 之后（此时引擎已 `require("screen_map")`）再 `pcall(require, "screen_map")` 拿**引擎那张表**挂钩子；另加一句 `pcall(attach)` 兜底（director 早于插件加载 / 本次会话已进过地图）。
    - ⭐ **同类对照**：本项目**其它插件全写对** —— `Demon_Sentinel:260` / `Fallem_Knight:75` / `iron_tower:38` / `all_talents_active:1795` / `hero_stats_enhanced:1530` 都是 `pcall(require, "screen_map")`。
    - 全库排查命令：`grep -rn 'require(\s*["'"'"']all-' --include=*.lua .`（要求**零命中**）。守卫：`.workbuddy/verify_viper_module_names.lua`（源码结构断言 + 「两个模块名=两张表」机制复现）。
  - 立绘帧布局（⚠ 2026-10-01 修正）：原版源文件 **274×386 整幅**，内容约 254×371 @ **(10,8)**。
    **走路线 C（`add_image`）时：PNG 必须做成 274×386 全画布**（内容贴到 (10,8)），`trim = {0,0}` ——
    别再用「给 254×371 内容区 + trim={(274−254)/2,…}」那套，`add_image` 会把整张按 trim 二次偏移 ⇒ 溢出。
    （走路线 B（自建真图集）时才写 `trim`，且必须满足 `size == f_quad + trim`。）
  - 图注册走 `register_ui_images()` 的 `UI_IMAGES` 表：`{ name="deadeye_room_portrait", file="…png", trim={0,0}, size={274,386} }`（全画布，见上）。
  - **立绘素材要有背景**：只画角色的抠图（透明/白底）放进框里会显得"底下空着"——本体 `portrait_notxt_*` 都是**背景烘死的整幅场景**。现成来源：`<FL8.0 目录>`（KR3 Origins 内核的 Dove 移植版，已移植 KR1 系英雄；本机在 `C:\Users\29140\Desktop\FL8.0电脑版`）里的 `kr3-desktop/assets/images/fullhd/screen_map_hero_room_<hero>-1.png`（**320×480 RGB**，帧名 `hero_room_portraits_big_hero_<hero>_0001`，图集 `rebborn_heroes_room.lua`）。落到 KR1 槽位：**cover + 居中裁剪**成 **254×374**（`scale = max(254/320, 374/480)`），再 `trim = ((274−254)/2, (386−374)/2) = (10, 6)`。
  - 读图集帧元数据别硬啃 `.luac`（`loadfile` 出来是**返回空**的 chunk）。两个通道：**首选** `.workbuddy/dump_atlas_entry.py <图集.luac> <帧名…>` —— 用游戏 `lua51.dll` 直接加载 `.luac` 并原样打印该帧元组，拿到的是**引擎真正读到的值**（帧格式见 `lib/klove/image_db.lua:554-561`：`{ a_name, f_quad={x,y,w,h,tex_w,tex_h}, trim={左,上}, ref_scale乘子, size={w,h} }`；`.luac` 里 `trim` 是四元组 `{左,上,右,下}`，引擎只取前两个，且 **`size` 与 `trim` 自洽**：`f_quad.w = size[1]-trim[1]-trim[3]` —— ⭐ **这条恒等式在真图集（路线 B / 本体图集）是硬约束**）；备选反编译文本版 `.workbuddy/ljdv2/output/<图集名>.lua`（`{ count, keys={帧名…}, values={{…}} }`，keys/values 同序、按 index 取；`values` 是**位置值元组**不是命名键）。
  - ⭐⭐ **拿到原版帧的 `size`/`trim`/`f_quad` 后，路线 C 的正确转写**：PNG 画布 = `size`；内容 = `f_quad` 尺寸，贴在 `(trim[1], trim[2])`；注册 `trim = {0,0}`、`size = size`。
    ⚠ **别把原版的 `trim` 直接抄进路线 C 的注册项** —— 那是路线 B/本体图集语义，抄过来就是二次偏移（ember map icon 的 `trim={78,46}` 遗留即此坑）。
  - 判"某帧属于哪个图集/哪个场景组（决定 `ref_scale`）"：`grep -l "<帧名>" _assets/kr1-desktop/images/fullhd/*.luac`（二进制也能命中得到图集名）→ 再看该图集出现在哪个场景的 `required_textures` 里。
  - 离线验收：`.workbuddy/verify_deadeye_hero_room.lua` 直接跑**真实模板 + 真实钩子**（`kui_db:init(path)` 后手动塞 `kui_db.templates["hero_room_view"] = 文件内容` 绕开 `love.filesystem`），断言注入条目下标 < name_label 下标、幂等、条目规格与原著同构，并带**反例自检**。⚠ ctx 必须给 `cjk`（`{ cjk = function(d,zh,ja,kr) return i18n:cjk(i18n,d,zh,ja,kr) end }`，引擎在 `screen_map.lua:1072` 这样造），模板第 5 行就要调，缺了直接 `attempt to call a nil value`。

- **殿堂「选择英雄」格子上的覆盖层**（2026-09-30 排查 johnny_deadeye「格子莫名发光」时摸清；`all-desktop/screen_map.lua:6633-6695`，都在缩略图循环之后 `ht:add_child`，画在所有缩略图之上）：
  - `check_image_1/2` = `create_slot_indicator(1|2, …)` = **队伍槽位**指示器：图 = `hero_room_thumbs_select_0000`（**粗黄框**，`border.scale = scale*1.1`）+ 右下角数字 `GGShaderLabel`；位置由 `select_hero(name)` 里的 `th.pos` 给，**数据源是存档 `user_data.heroes.selected`**。⚠ **槽 1 粘性**：队伍满 2 人后再点别人只替换槽 2（`table.remove(selected, 2)`），要换槽 1 得点「取消选择」。
  - `self.border_image` = `create_select_view("hero_room_thumbs_select_0000")` = **当前展示**的英雄（`show_hero` 里 `border_image.pos = th.pos`）。和槽位指示**用同一张黄框图** → 展示中的那格会出现**两圈同心黄框**（1.0× 与 1.1×），看着比只占一个槽的格子"更粗更亮" —— 这是引擎行为，不是 bug。
  - `self.hover_image` = `create_select_view("hero_room_thumbs_select_0003")` = **鼠标悬停**柔光（`v2.on_enter/on_exit`）。
  - 每格底子：`hero_room_thumbs_%04d`（缩略图，名字走 `U.splicing_from_kr(from_kr, …)`）+ `hero_room_thumbs_0000`（银灰格框）；关卡未通关再叠 `hero_room_portraits_lock`。布局 7 列、`spacing_x=46`、`spacing_y=50`、`scale=0.625`（`screen_map.lua:6562-6565`），行高即滚动步长。
  - ⚠ **省一次误诊**：「某英雄格子一直发光/选中状态不对」**先读 `%APPDATA%/LOVE/kingdom_rush_dove/slot_N.lua` 的 `heroes.selected`**，再怀疑代码。截图里鼠标停在哪格就有 hover 柔光，别当故障看。

- **升级经验门槛是所有英雄共用的全局表**（2026-09-30 定案）：`GS.hero_xp_thresholds`（`kr1/game_settings.lua:209`，累计门槛 `{300,900,2000,4000,8000,12000,16000,20000,26000}` 合计 89200）是**唯一一张、无 per-hero 字段**；判定 `all/script_utils.lua:1044`（只用 `h.level` 索引，不看英雄身份）、显示 `all-desktop/game_gui.lua:2275/2278`。⇒ 要只给**单个英雄**加减升级经验，**别动这张表**（一动就是全员）。做法：`HOOK(SU, "hero_level_up", fn)` 在入口对目标英雄（`this.template_name == "hero_<名>"`）把 `h.xp_queued × 1/(1-p)` 再交给 `next(store, this)`——原函数紧接着清零 `xp_queued`，不会重复放大；门槛表与经验条 UI 都不用改（代价：经验条数字比"真实战斗量"偏大 1/(1-p) 倍）。⚠ 若改成"门槛 ×(1-p)"则**必须同时**改 `game_gui` 的 `hero_xp_base/hero_xp_next`，否则条没满就升级。经验入账共 3 条路径（`SU.hero_gain_xp` / `SU.hero_gain_xp_from_skill` / `all/systems/health.lua:633` 击杀）——钩升级入口一次全覆盖，比逐条改入账点稳。⚠ `mods/local/资源/output/**` 下的同名 `script_utils.lua`/`game_gui.lua` 是**反编译副本、非运行时代码**，别当第二消费点去改。`hook_utils.HOOK` 不幂等 → init 里用全局标记（`_G.__xx_hook`）防重挂（插件重载会重跑入口文件，local 标记会丢）。

- **⚠⚠ 改移动速度绝不能直接写 `motion.max_speed`**（2026-09-30 实测踩坑，johnny_deadeye 骑马 +20% 用户反馈"没快很多" → 实为**完全没生效**）：`U.walk`（`all/utils.lua:1054`）用 `step = e.motion.real_speed * dt`，而 `motion.real_speed` **只在实体 insert 时**由 `all/systems/last_hook.lua:45-47` 从 `max_speed` 同步一次，此后**没有任何系统每帧刷新它**。⇒ 直接赋 `this.motion.max_speed` 对移动速度**零效果、零报错、零日志**，极易被误判成"数值调太小"。正确写法（这些封装都会同步刷新 `real_speed`）：`U.speed_mul_self(e, f)`（max_speed ×f）、`U.speed_div_self`、`U.speed_inc_self`/`dec_self`、`U.update_max_speed(e, v)`；公式 `real_max_speed = km.clamp(1, 10000, (max_speed + buff) * factor)`。临时加速后还原也用 `U.update_max_speed(this, original_speed)`，别直接赋值。同理 `motion.factor`（乘法减速）走 `U.speed_mul/div`，`motion.buff`（加减速）走 `U.speed_inc/dec`——**改哪个字段就用对应的 U 封装**，别自己写赋值。

- **加"局内可见"的自定义 sprite（世界渲染，无需图集）**（2026-09-30，johnny_deadeye 的脚下提示光环）：① 生成 png（本机用 ImageMagick `magick`，务必转 8-bit：`magick x.png -depth 8 PNG32:x.png`）；② 复用插件已有的 `register_ui_images()`，在 `UI_IMAGES` 里加 `{ name = "<帧名>", file = "<文件>.png" }` → 内部 `I:add_image(name, img, "<插件名>", 1)`；③ 模板加 sprite 层：`E:clone_c("sprite")` + `name = <帧名>` + `animated = false` + `hidden = true` + `offset`/`scale`，再 `tt.render.sprites[N] = ...`；④ 运行时改 `sprite.hidden` 即可显隐。关键事实：**`I:add_image` 注册的图可直接给世界 sprite 渲染**（引擎自己的 texts 机制就这么干：`all/systems/render.lua:142-166`）；`trim = {0,0}` 是安全的（渲染只读 `trim[1]/trim[2]`，见 `game_gui.lua:2799`、`screen_map.lua:4938`）；绘制顺序 `_draw_order = 100000 * (s.draw_order or i) + entity.id`（`render.lua:178`）→ 不设 draw_order 就**按数组下标排**，数组靠后的天然在上层；`add_image` 内部 `atlas_uses += 1`，等于常驻引用，不会被场景卸载。⚠ `E:clone_c("sprite")` 默认 `anchor = v(0.5,0.5)`、`animated = true`、`hidden = nil`、`scale = nil`，clone 后按需覆写；显隐用 `hidden = true/false`。
  - ⚠⚠ **`image_db` 的 `unload` 会把 `db_atlas[name]` 整个置 nil**（`lib/klove/image_db.lua:417`）—— `atlas_uses` 归零即触发。**注册一次不等于永久有效**：切场景/重进关卡后图可能已没了。⇒ **两条补注册路径都要兜底**：① `kui_db.get_table`（殿堂懒加载时补）② `screen_map.refresh_hero_button_state`（地图头像 icon 时补）。两处都写，别只写一处。
- **叠层/充能类技能的粒度必须与文案口径一致**：连发攻击（`for si = 1, a.max_shoots`）里若**每发**都推进层数，一轮就连满 → 玩家看不到"逐步"，且极易被误判为"技能没生效"。要"每轮攻击 +1 层"就写成 `tick = (si == 1)`：第 1 发推进、同轮其余子弹只读倍率；换目标清零与"推进"写在同一个 helper，避免漏调用点。
- ⚠ **但"叠层加伤"未必是用户想要的粒度**（2026-09-30 johnny_deadeye 实例修正，**两次迭代**）：用户先否掉"连续打同一目标叠层加伤（+15%/层、换目标清零）"，改为"计数攒特殊弹"；随后又明确**左轮要按「五个整轮普攻」计数，而不是每五发子弹**（霰弹仍按每发，用户说"霰弹不用处理"）。最终口径：**左轮每 5 轮普攻后的下一轮 → 该轮六发全部转真实伤害 ×1.4；霰弹每 4 发后的下一发 → ×1.5 + 58 半径爆炸**。
  **粒度 = 调用点位置**（计数器本身粒度无关，只认调用次数）：每发 → 调用写在 `for si = 1, <连发数> do` 内；每整轮 → 调用提到 `for` **之前**存局部 bool，循环内 `if round then` 让该轮全部子弹生效；只有 1 发时（如 `tick = (si == 1)`）也是同一套写法。**动手前先跟用户确认粒度**，别猜。
  其它要点：① 周期 = N+1（阈值语义"每 N 次后的下一次"），霰弹阈值取「连发数 − 1」（5 发→4）就能让特殊弹稳定落在每轮最后一发；② 计数存实体上（`this._bullseye = { a = 0, b = 0 }`）并**跨连发/跨目标持续累积**（不因换目标或中断清零），两种模式各自独立；③ 计数函数挂到 **script 表**上（`scripts.<name>.fn` + 文件内 `local fn = scripts.<name>.fn`），否则离线单测断言不到；④ 离线断言除了行为断言，再加**源码结构断言**（`io.open` 读脚本、比对调用点在其 `for` 行的前/后）——粒度这种"位置决定语义"的改动，这是最直接的证据。落地实现与 49 项离线断言见 `.workbuddy/verify_deadeye_bullseye.lua`；范围伤害/真实伤害/落地印记的完整范式见技能 **`kr-dove-bullet-aoe-fx`**。

- ⚠ **经验倍率有两层，别以为都要填 —— 远程攻击只认弹丸那一层**（2026-10-01 johnny_deadeye 追查定案）：
  XP 的唯一结算点是 `all/systems/health.lua:627-634`（`amount = d.damage_applied * d.xp_gain_factor`），倍率挂在 **damage 记录** 上，而 damage 记录有两条来源：
  - **攻击层** `melee.attacks[i] / timed_attacks.list[i].xp_gain_factor` → 读者只有近战/范围处理器：`all/script_utils.lua:2050`（`SU.y_soldier_do_single_area_attack`）、`:2214`/`:2267`（`..._loopable_melee_attack`）、`:2385`（`..._single_melee_attack`）。
  - **弹丸层** `bullet.xp_gain_factor` → `all/script_utils.lua:615`/`:657`/`:671`（三个 `create_bullet_damage*` 都写 `d.xp_gain_factor = bullet.xp_gain_factor`）。
  ⇒ **远程 `timed_attacks` 路径没有任何地方读攻击层的值**（通用处理器 `SU.y_soldier_timed_attacks`@`:1939` 与 `SU.y_soldier_do_timed_attack`@`:1888` 都不读），弹丸又是 `E:create_entity(a.bullet)` 直接从模板生成 ⇒ **只有弹丸模板的 `bullet.xp_gain_factor` 生效，攻击层那个是死旋钮**。
  **引擎不会自动把攻击层值抄给弹丸** —— 那行只在个别原版英雄脚本里手写（`kr1/hero_scripts.lua:30330`、`:23718`、`:23764` 的 `b.bullet.xp_gain_factor = a.xp_gain_factor`）→ 想让它生效，得在自己射击循环 `queue_insert` 前自己补这行（补了之后弹丸模板那个就作废，**二选一**）。
  ⚠ 移植时**别只因为"原版模板里有"就照抄**：原版 KR1 重制版 deadeye 两个都写了（弹丸 2 / 攻击 1.5），但攻击层那个在**原版同样没被消费**（原版左轮循环 `game_scripts.decompiled.lua:20002-20018` 也没有拷贝行）→ 照抄会把死旋钮一起搬过来。
  ⚠ **"每级成长"型倍率会覆盖模板值**：弹药类技能若在 `level_up` 里写 `get_template(bullet).bullet.xp_gain_factor = skill.xp_gain_factor[sl]`（原版 `game_scripts.decompiled.lua:19675` 同款），模板上的静态倍率就**只在解锁前有效**；而解锁前该攻击通常 `disabled` → 等于从来没有生效窗口，又是个死旋钮。
  ⚠ 配置探针（`probe_deadeye_config.py`）的"死旋钮"判定只看 **config 键有没有被 `balance.lua` 的 `num/nums/bool/int/str` 消费**，**不追 `B.xxx` 有没有被下游读** ⇒ 这类"赋了值但没人读"的键探针抓不到，必须人工把消费链追到 `health.lua`。
  **处置（2026-10-01 已落地，用户选「A 删死键」）**：把两个死键从「config 三表 + `DEFAULTS` + `num()` 映射 + `hero_templates` 引用 + 对齐断言 SPOT」**六处一起删干净**（漏任一处：`hero_templates` 里会变成 `= nil` 而静默、SPOT 会 `resolve` 到 nil 报 FAIL）→ 面板项 **48 → 46**。**只保留弹丸层那一个**（`revolver_bullet_xp_gain_factor`）。判据：删完 `grep -rn "<死键名>"` 必须只剩 backups 目录。⚠ 删掉键后**记得同步 README 里的「N 个强度项」计数**（两处）。

### ⭐ `hero_room` 图集号段表（新英雄挑槽位必查）

> ⭐⭐ **UI 图（殿堂/地图按钮/HUD 头像）的完整规格见
> [`references/hero-ui-images.md`](references/hero-ui-images.md)** ——
> 三条互不兼容路线（借用本体帧 / 自建真图集 / `I:add_image`）、四类槽位权威规格、
> `tt.info.portrait` vs `hero_portrait` 的区分、槽位撞号事故、生命周期兜底，全在那里。

各代号段**互不重叠**（挑错代 = 撞别人图 / 查无此帧 → 点殿堂崩）：

| 命名空间 | thumb / icon | 大立绘 `portrait_notxt_*` |
|---|---|---|
| 无前缀（**KR1**） | `0000`–`0013` | `0001`–`0013` |
| `kr2_` | `0001`–`0018` | `0001`–`0016` |
| `kr3_` | `0001`–`0016`、`0019` | `0001`–`0016`（**无 0017/0018**） |
| `kr4_` | `0001`–`0017` | `0001`–`0017` |
| `kr5_` | `0001`–`0019` | `0001`–`0019` |

⚠ 图集里**没有** `hero_room_portraits_XXXX` 这个名字 —— 只有 `portrait_notxt_*`（大立绘）与
`hero_room_portraits_name_0000`/`_lock`（名字条/锁）。⚠ `hero_data` 的三字段
`portrait == thumb == icon` **恒等**（本体 82 条无一例外），三处同步改。

## D. 验证工具（.workbuddy/）

- `lua_syntax_check.py`：lua51 ctypes 编译校验（多文件）。
- `check_atlas_blank_frames.py`：每帧不透明占比（查空帧/丢帧）。
- `semifit_hero_marine_canvas.py`：半紧画布改写器（换英雄改常量复用）。
- 图集描述 170 帧级校验脚本思路：f_quad 落在 a_size 内、size 语义一致。

## E. 进度锚点

- 钢铁队长：已上线迭代（0.55 体型/双连发/伤害单源/护盾环修完）。**用户 2026-09-28 宣布暂停**（Dove 侧无法扩展更多主动技）。
- 自由猎人：**trabuco_hero 已上线迭代中**（7 轮实测修复）。第 7 轮根因：contact sheet 目测帧段错位（run 段落在 Shot_Down 里）→ 已换 XML 权威帧段表（见 C 节）。伤害数值用户自定。
- ⚠ **用户决定：自由猎人全技能被动化，无主动技按钮**——形态切换按目标自动选（update 脚本+防抖冷却）、吞乙金低血自动触发。denas_summon_skill 的自建 PowerButton 先例留档不用。
- 全新英雄插件接口清单 = 工作区根 `全新英雄插件接口分析.md`（含 health.on_damage 免死钩、bullet.damage_hooks、SU.y_hero_death_and_respawn 自动重生、boss_crocs_hero 殿堂范式）。

## 技能经验入账 & mod 叠加模型（2026-10-01 从工作区 MEMORY 迁入）

### ⭐ 技能奖励：`SU.hero_gain_xp_from_skill` 必须**显式调用**

`all/script_utils.lua:1005-1019` 定义。

- ⚠ **引擎永不自动调它** —— 英雄脚本必须**自己显式调用**。
- 位置：**前摇等待之后、`a.ts = start_ts` 之前**。
- ⚠ **例外**：`timed_attacks.list[*].xp_from_skill = "<技能名>"`（2 处）引擎钩子会**自动**按技能等级给经验
  —— 两类可并存（会员兼容 ember 就是两套都用：`xp_from_skill` + 脚本内显式调）。

### ⭐ `xp_gain` vs `xp_gain_factor` 是两个字段

- `xp_gain` —— **数组**，每次施法固定奖励（按技能等级取值）；
- `xp_gain_factor` —— **标量**，每级经验倍率。

全局放大两层：`store.hero_xp_multiplier`（难度 × 关卡序号）× 插件 `balance.xp.gain_factor`。
⚠ **升级门槛 `GS.hero_xp_thresholds` 全体共用，别动它**（做法见上文 149 行）。

### ⭐⭐⭐ mod 是否叠加 —— 别再踩「×28 杠杆」的坑（2026-10-01 实测纠错）

**曾经写错过这里**：一度断言「`aura` 每 `cycle_time` 反复 `create_entity(mod)` ⇒ 稳态叠
`duration/cycle_time` 个 ⇒ 实际 DPS = 单次伤害 × 每 mod 次数 × N（ember 岩浆 ×28）」。**
这是错的**，用户游戏内实测「每秒只有一个 mod」推翻了它。

**真正的判据**：`all/systems/mod_lifecycle.lua:60-86`，`on_insert` 对每个同类 mod 走：

```lua
if     mdf.max_duplicates     then ... end
elseif mdf.allows_duplicates  then ... end
elseif mdf.resets_same        then  m.modifier.ts = store.tick_ts; return false
else                                return false end
```

⚠⚠ **`modifier.resets_same` 的默认值是 `true`**（**组件默认**，`all/components.lua:878`，
**不是写在某个模板基类里的** —— 只在 `register_t("modifier")` 的字段里找会查不到，容易误判成
「走最后的 else」）。⇒ 普通 mod **默认唯一**：目标上已有同类 mod 时，
**只刷新它的 `m.modifier.ts`、`return false`、连 `main_script` 都不跑**。

**结论**：
- 「每 tick 无脑 `queue_insert(mod)`」是**安全**的（引擎自动去重），写起来最省事。
- 目标被反复覆盖时 mod 会**无限续命**（`duration` 永不到期）；目标离开来源后才开始倒计时
  —— 这正是「灼烧/中毒残留」该有的语义，但**要意识到 duration 在持续接触时不代表实际存活上限**。
- **DPS = 单次伤害 ÷ `damage_every`**（不分等级、不乘任何叠加数）。
  ember 岩浆 5/7/9 每 0.2s ⇒ **25 / 35 / 45**（探针 `.workbuddy/probe_ember_dps.lua` v3）。
- ⚠ **想真做"叠层"效果**（如中毒 3 层），必须**显式声明** `modifier.max_duplicates = N`
  或 `allows_duplicates = true`（范式见 `kr1/archer_towers.lua:97` 的 `mod_ranger_poison`：
  `max_duplicates = 3`）。默认状态下写"叠 3 层"是**幻想**。

**两条相邻的支撑事实**（仍成立）：

1. `on_queue_unconditional`（`all/systems/health.lua:526`）只做 `root_entity_map` 记账、
   **不拦截插入** —— 它**不是**去重的地方，别拿它当"叠加模型成立"的证据。
2. `mod_hps.insert`（`all/scripts.lua:6292`）**满血时直接 `return false`**
   ⇒ 满血目标身上不会产生回血 mod（不浪费），**掉血后才开始回血**。

### 离线验证两个必做桩

跑英雄 `update`（**永续协程**）时：

1. 每步推高 `render.sprites[*].runs` —— 否则 `U.y_animation_play` 的
   `while a.runs <= times` **永久挂死**；
2. `this.nav_rally` 给哨兵 `{new = false}`。

同步 stub `U.find_enemies_in_range`。
⚠ `E.Load` 前必须先 `require('i18n').load_locale('zh-Hans')`，
否则崩 `all/i18n.lua:41 attempt to index local 'l' (a nil value)`。
