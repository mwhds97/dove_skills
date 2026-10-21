# 英雄 UI 图（殿堂 / 地图按钮 / HUD 头像）完整规格

> 从工作区 MEMORY.md 迁入（2026-10-01），原为「英雄殿堂 / UI 图」整节。
> MEMORY.md 只留指针，细节全文在此。

## ⭐⭐⭐ 三条互不兼容的路线 —— 先选路线再动手

此前 MEMORY 里出现过自相矛盾的记载，根源就是**把三条路线混为一谈**。

### 路线 A · 借用本体帧（案例 `Ten_Plagues_Isfet`）

**适用**：本体图集里已有该英雄整套 UI 帧。

`hero_data` 写 `thumb=N, icon=N, portrait=N, from_kr=K` 即可命中
`krK_mapButtons_portrait_hero_%04i` 等**真帧**，**零自制贴图**。

- 实测 Isfet：`portrait=thumb=icon=16, from_kr=4` → `kr4_*_0016` 源图**有真内容**（紫袍木乃伊 = Isfet 本人）。
- 运行时只用 `view.image_offset = vec(ox, oy)` 微调
  ⚠ 是 KView 的**绘制偏移字段**，**不是** `trim`。

### 路线 B · 自建真图集（案例 `Alric_Overhaul`）★ 自制英雄**推荐**

**适用**：自制英雄、需要精确构图。

`_assets/images/` 放 `.lua`（帧表）+ `.dds`（贴图），与引擎原生图集**同构**：

```lua
["Alric_Avatar_2"] = { a_name="Alric_Portrait.dds", size={226,184},
                       trim={78,46,76,70}, f_quad={256,173,72,68} },  -- trim 是 4 元素
```

- ⭐⭐ **`size == f_quad + trim` 是硬约束**（72+78+76=226 ✓、68+46+70=184 ✓）。
  `trim` **有意义且必须**。
- 加载：`I:load_atlas(ref_scale, path, name)`
  （`alric_image_loader.force_load_atlas`，先 `reset_atlas_group` 清同名组）。
  `Alric_Portrait` 用 `ref_scale=1`。
- 微调：`adj()` 写 `f.ref_scale = base*smul`、`f.trim[i] = base + o/ref_scale`
  （存 `_alric_ui_base` 快照保幂等）。
  `alric_asset_hooks.lua` 还 HOOK 了 `I.load_atlas / queue_load_atlas / preload_atlas*` 做路径重写。

### 路线 C · `I:add_image`（现状：ember / viper / deadeye）

**适用**：自制英雄，只有现成 PNG 且构图已合适。

语义最弱，**只有整张 PNG**：

`image_db.lua:726-743` **忽略调用方给的一切布局数据**：

```lua
quad  = G.newQuad(0, 0, w, h, w, h),   -- w,h = PNG 实际尺寸（不是 size！）
trim  = {0, 0},
size  = {w, h},
```

绘制时（`lib/klove/kui.lua:671`）：

```lua
G.draw(self.image, ss.quad, ss.trim[1]*ref_scale, ss.trim[2]*ref_scale, 0, ref_scale)
```

⇒ 画的**永远是整张 PNG**，`ss.trim` 只被当作**整体位移**。

- ⇒ PNG 必须做成**原版整幅画布**（偏移靠留白表达），`trim` 恒 `{0,0}`。
- ❌ 给内容区 + `trim={78,46}` ⇒ **整张跑出相框**（ember 地图按钮头溢出即此）。
- ⚠ **「trim 恒应为 {0,0}」只在路线 C 成立**，别推广到路线 B。

**两种口径对比**（插件后来覆写 `ss.trim`/`ss.size` 只是改元数据，改不了 quad）：

| 口径 | PNG | trim | 结果 |
|---|---|---|---|
| ❌ 旧（内容区紧裁） | 72×68 | `{78,46}` | 72×68 图被移到 (78,46) ⇒ **整张跑出相框** |
| ✅ 新（原版整幅画布） | 226×184 | `{0,0}` | 内容天然落在 (78,46) ⇒ 正确 |

### ⭐ 选型

本体已有帧 → **A**；自制 + 要精确构图 → **B**；自制 + 只有现成 PNG 且构图已合适 → **C**。

---

## 四类槽位权威规格

路线 A/B 都按此；路线 C 见上「必须全画布」。

| 家族 | 原版画布 | 内容 @ bbox | 用途 |
|---|---|---|---|
| `mapButtons_portrait_hero_*` | 226×184 | 72×68 @ (78,46) | 关卡地图英雄按钮（`screen_map.lua:992`） |
| `hero_room_thumbs_*` | 84×84 | 60×63 @ (12,11) | 殿堂/关卡选择缩略图（`:6586`） |
| `portrait_notxt_*` | 274×386 | ~254×371 @ (10,8) | 殿堂大立绘 |
| `hero_portraits_*` | 144×142 | 87×87 @ (28,22) | 战斗 HUD 英雄槽 = 本体「一键召唤」按钮源（`game_gui.lua:2076 HeroPortrait` 读 `tt.info.hero_portrait`） |

### ⚠⚠ `tt.info.portrait` ≠ `tt.info.hero_portrait`（两字段只差 `info_`，极易混）

> 2026-10-01 踩过。

- `tt.info.portrait`（注册图 `ember_info_portrait`，**无 scene/size/trim ⇒ 原尺寸自适应绘制**）
  = **战斗内左上角信息栏圆形头像**；
- `tt.info.hero_portrait`（注册图 `ember_portrait`，`scene=game_gui`，144×142 全画布）
  = 英雄槽/召唤按钮侧（`HeroPortrait`）。

用户说「信息栏头像 / hud 头像」时**要先分清是哪一个**再动手。

### ⭐⭐ infobar 头像原版权威规格

**96×96 画布 / 内容 66×66 / trim{15,15}**（实测 `kr1-desktop/images/fullhd/gui_portraits.luac`
的 `info_portraits_heroes_%04i`，7 帧全一致；
帧结构 `{a_name, f_quad={x,y,w,h,TW,TH}, trim={tx,ty}, ref_scale, size}`）。

插件侧因走 `I:add_image`（无 trim），要对齐原版就**把 PNG 烘成 96×96 + 内容 66×66 居中**（四周留 15px 透明边）。

⭐ ember 实际采用口径：**68×68 顶满**（`ember_info_portrait.png`，见 2026-10-01 日志）。

### `scale` 与场景

`scale` = 场景 `ref_res / TEXTURE_SIZE_ALIAS[贴图组目录]`：

- `game_gui` → **0.71111**（768/1080）
- `screen_map` / `slots` / `loading` → **1**

⚠ **不许 require 场景模块**，用静态映射表。

### 构图

⚠ 构图要对（thumb/icon 应为**头肩特写**：顶贴上缘、脸居中略偏下、底到肩，
**非全身像 / 非局部色块**）。KR1 ember 立绘源 = `screen_map_hero_room_ember-1.png` 的 `(820,1581,477,504)`。

⚠ 路线 C 的反例清单（曾写错、已修为全画布）：ember / deadeye / viper 的
thumb / map_icon / room_portrait / viper_portrait。

---

## 生命周期与取图原则

- ⚠ **图集 `unload` 会把 `db_atlas[name]` 置 nil**（`image_db.lua:417`）
  ⇒ 两条补注册路径都要兜底：① `kui_db.get_table`（殿堂）② `screen_map.refresh_hero_button_state`（地图 icon）。
- ⭐⭐ **取原版 UI 帧只认像素，不认模板里的 frame 名**（逐帧裁图 → 目视，**别整组批量偏移**）。
- ⭐ **殿堂特技描述必须由数值算出来**；技能数组取**满级 = 最后一项**；
  汉字数字表**必须 `[0]="零"` 起**。生效 = `hook.E.load`。
- ⚠「英雄格子莫名发光 / 黄框」**先读存档再改代码**：黄框 = 队伍槽位，柔光 = `select_0003`。

---

## ⚠⚠ 槽位帧名必须全局唯一

`image_db:add_image`（`lib/klove/image_db.lua:724`）**无重名校验**、
`db_atlas[name] = ...` 直接覆盖；插件按 `priority` **升序加载 → 后者胜出**。

⇒ 新英雄取号前**必须查全库**：

```bash
grep -rn 'name = "hero_room_thumbs_00\|name = "mapButtons_portrait_hero_00' --include=*.lua KingdomRushDove/mods/local/
```

⚠ **必须带 `name =`**，否则混入 `hero_stats_enhanced` 对本体帧的**引用**（读，非注册），无法判断真实冲突。

**当前占用**：`0014` = ember_hero ｜ `0015` = hero_viper ｜ `0021`/`0023` = johnny_deadeye(icon/thumb)。

⚠ 改号段要同步**硬编码号段的校验脚本**
（如 `.workbuddy/verify_viper_slot_names.lua` 写死 14/0014，不同步会**假绿**）。

### 撞击案例（2026-10-01 已修）

`hero_viper` 与 `ember_hero` **同时**注册了 `hero_room_thumbs_0014` 与 `mapButtons_portrait_hero_0014`。

| 插件 | priority | 原 thumb / icon | 现状 |
|---|---|---|---|
| `johnny_deadeye` | 20 | `0023` / `0021` | 不变（唯一，无冲突） |
| `hero_viper` | **21** | `0014` / `0014` ← 原被覆盖 | **已改 `0015` / `0015`** |
| `ember_hero` | **22** | `0014` / `0014` ← 原胜出 | 不变（`0014` 归 ember 独占） |

**修法**：把 `hero_viper` 从 `0014` 改到 `0015`（新插件让位改为老插件让位，
因 ember 的 14 已推送且 README 记录为「KR1 段下一个空号」）。
viper 侧三处同步（`hero_data_entry()` + `UI_IMAGES` + 注释），并同步校验脚本。

**教训**：新增英雄插件时，槽位号必须检查**全库已用号段**，不能只在「本代号段」里挑下一个空号。

---

## 号段表

见 SKILL.md 的「⭐ `hero_room` 图集号段表」。
⚠ 图集里**没有** `hero_room_portraits_XXXX`，只有 `portrait_notxt_*`（大立绘）
与 `hero_room_portraits_name_0000`/`_lock`（名字条/锁）。
