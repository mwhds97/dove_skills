---
name: kr-dove-ui-panel
description: 在《王国保卫战 Dove》(KingdomRushDove) 插件里从零手写 UI 面板（弹窗 / 选择页 / 房间界面）的成套做法，以及**复用 KR6(Genesis) 原版图集素材**的完整链路。核心覆盖六件最容易翻车的事：①⭐⭐⭐ **缩放素材只能用 `scale`，`self.size` 对绘制完全无效**（`KView:draw` 用 `ref_scale = ss.ref_scale * image_scale`，`set_image` 的 size 只管命中判定与 anchor ⇒ 赋 `.size` 会"看起来改了但游戏里素材仍按原生像素画、大一圈"；换帧后还必须重算，因为 `set_image` 会把 size 重置成新帧原生尺寸）；②Dove 的九宫格类叫 `GG9View`（不是 KR6 的 `GG59View`），`slice_rect = r(左,上,中列宽,中行高)` 且中间格是**平铺缩放**、尺寸不足**返回 nil**；③`font_db:f()` 查不到字体**只 log.error 后 return nil** ⇒ 崩在 `gg_views.lua:214 attempt to index field 'font'`，真线索在 `font_db.error Font X not found`，合法别名白名单在 `all-desktop/data/font_subst.lua`；④点击必须**给视图实例赋 `on_click`** + 子视图设 `propagate_on_click=true`，否则"面板能开、点不动"；⑤`GGDoneButton` 的 `label_text` 必须 **new 时传参**；⑥`all/storage.lua` 是单例模块可直接 `save_slot`。另含**离线出图工作流**（PIL 重实现 GG9View / fit_width 语义渲染成品预览图，改 UI 前先自己看图，不靠用户截图来回；⚠ 预览必须复现引擎真实绘制语义否则"预览对、游戏错"）与**布局几何自检**（查出界/重叠/越界 + 画示意图）。在**大地图（`screen_map`）上加自定义入口按钮**（判据用 `screen_map.window` 而非 `main.screen_map_entered`；全局 `_G.screen_map` 可能被 require 换成空表，要从 `package.loaded` peek 真身；参照点用本体存的 `_change_btn`/`hero_but` 而非扫 children；挂载链要留痕否则"入口消失"零日志）；触发场景：写 Dove 插件面板、弹窗、选择界面、槽位、列表行、按钮；想用 KR6 原版 UI 素材但不知道 Dove 支不支持九宫格；**素材显示尺寸不对/大一圈/压到别处**；面板点了没反应；按钮上没字；面板字体报 nil 崩溃；布局元素重叠/跑到框外；想先看效果再进游戏验证。
agent_created: true
---

# Dove 插件自建 UI 面板 + 复用 KR6 原版图集

面板改版只能靠用户截图反馈，一轮来回很贵。本技能的核心价值是**在进游戏之前
先把几何和视觉都验证掉**：几何用布局自检脚本，视觉用 PIL 离线渲染。

---

## 0. 铁律：写 UI 前必须扫本体真实资源名，别猜

**代价实录**：曾臆造 `ui_bg_frame_square` / `ui_menu_btn_blue` /
`KScrollList:item_height` —— 全是本体不存在的名字，写出来才发现。

可靠来源（都是纯文本，可直接读）：

| 要什么 | 去哪找 |
|---|---|
| 真实帧名 + 类名 + 布局范例 | `KingdomRushDove/kr1-desktop/data/kui_templates/*.lua` |
| 自定义视图类实现（GGButton/GGDoneButton/GG9View/GGPanelHeader…） | `all-desktop/gg_views_custom.lua`、`all/gg_views.lua` |
| 视图基类机制（hit_all / 点击分发 / 滚动列表） | `lib/klove/kui.lua` |
| 字体别名白名单 | `all-desktop/data/font_subst.lua` |
| 字体文件真名 | `KingdomRushDove/_assets/all-desktop/fonts/`（文件名 = `font_files` 的键） |
| KR6 素材帧 | `Kingdom Rush Genesis/Kingdom Rush Genesis/_assets/kr6-desktop/images/fullhd_bc3/*.lua` |

⛔ **两个假线索**，别用：
- `_assets/assets_index.lua` **只列文件、不含图集帧名**。
- 离线 `love_stub` **不加载 KRAB 二进制索引 ⇒ 静态查帧名全是假阴性**
  （连本体自己在用的 `mapButtons_notxt_0010` 都查不到）。

### ⭐⭐⭐ 0.1 帧名是否真的存在 —— 用 KRAB 解析器，别猜

这是**踩过两次**的坑，而且崩得很晚、报错点在引擎里，用户实机才发现：

```
kui.lua:529  attempt to index local 'ss' (a nil value)
image_db.error  Sprite <帧名> was not found in the atlas db.
```

**根因常常不是拼错，而是「同功能帧在 KR6/Dove 里前缀不同」**：

| 用途 | KR6 名 | Dove 名 |
|---|---|---|
| 士兵头像 | `gui_bottom_info_image_soldiers_0068` | `kr6_info_portraits_soldiers_0068` |
| 爆头 pop | `pop_headshot` | `pop_instakill`（`all/templates.lua:710`） |

⇒ **权威做法：解析 Dove 的 KRAB 二进制索引**（格式见
`lib/klove/atlas_binary.lua` 头部注释）：

```
KRAB  u8 version  u32 frame_count  u16 atlas_name_count [u16 len+bytes]*
frame_count 条：u16 len+name, u16 atlas_idx, u16*4 f_quad, u16*2 a_size,
                u16*2 trim12, f32 ref_scale, u16*2 size, u16 alias_count [u16 len+bytes]*
```

本技能包 `scripts/_krab_check.py` 已实现（含缓存）：

```bash
python .workbuddy/_krab_check.py --rebuild          # 建索引（473 bin ⇒ 27万+ 帧名）
python .workbuddy/_krab_check.py <帧名1> <帧名2>      # 判定存在性
python .workbuddy/_krab_check.py --list <子串>        # 列出含该子串的帧名
python .workbuddy/check_kr6_frames.py               # 插件级体检（扫全部帧承载字段）
```

**要把帧「看」出来**（判断某块官方底板能不能直接拿来做背景）用同目录的
`parse_krab_atlas.py` —— 按 `f_quad` 从 `.dds` 里裁图，Pillow 直接能解 DXT：

```bash
python .workbuddy/parse_krab_atlas.py list  <bin> <关键字>          # 带 size/trim/ref_scale
python .workbuddy/parse_krab_atlas.py crop  <bin> <帧名> out.png 2   # 2 倍放大出图
python .workbuddy/parse_krab_atlas.py sheet <bin> <关键字> out.png   # 关键字批量出图
```

⚠ 图集图片常叫 `xxx-1.dds`（脚本已自动回退）；**Python 不认 `/c/tmp`**（要写 `C:/tmp`）。
2026-10-21 实锤：迈达斯之手框内的底板就是靠它找到的 `base_info_bar_bg`
（`gui_common`，154×24 纯黑圆角），直接 `KImageView` 拉伸铺进框里、零分发成本。

⚠ 判定时要**同时接受动画前缀**：`render.sprites[1].prefix` 存的是前缀
（动画键 = `prefix .. "_" .. name`，`all/systems/render.lua:398`），
所以 `kr6_sol_decal` 这种"查不到完整帧"其实是合法前缀（帧是 `kr6_sol_decal_0001`…）。

⚠ 另一个高频坑：**KR6 逻辑尺寸 ≠ Dove 帧尺寸**。Dove 帧的 `size` 是物理像素，
要乘 `ref_scale` 才等于逻辑尺寸（如 Dove `136×130 @ref 0.7031` ↔ KR6 逻辑 `96×91`）。
判"是不是同一张图"除了名字对应，最好**像素比对**（`magick compare -metric RMSE`）。

---

## 1. 九宫格：Dove 有 `GG9View`

**这是反直觉的**：全局搜 `9slice` 在 Dove 里**一个结果都没有**（那是 KR6 的
**命名约定**，不是类名），所以很容易误判"Dove 不支持九宫格"。其实类叫
**`GG9View`**（KR6 叫 `GG59View`）。

```lua
-- all/gg_views.lua:661
GG9View = class("GG9View", KView)
GG9View.static.init_arg_names = {"image_name", "size", "slice_rect"}

local view = GG9View:new("my_frame", v(920, 752), r(57.6, 84.35, 22.8, 226.75))
```

### slice_rect 的语义（**最容易搞错**）

`V.r(左, 上, 中列宽, 中行高)` —— **不是** CSS 那种"四边厚度"。

```lua
-- all/gg_views.lua:703-706
local p1x, p2x = slice.pos.x, slice.pos.x + slice.size.x
local tw1, tw2, tw3 = p1x, slice.size.x, imgw - p2x
```

即：`左` = 左边距宽度，`中列宽` = 可拉伸区宽度，右边距 = 素材宽 - 左 - 中列宽。

### 渲染算法（照抄 `all/gg_views.lua:703-745`）

```
cw = round((out_w - tw1 - tw3) / tw2)          -- 中间格平铺几列
sw = (out_w - tw1 - tw3) / (cw * tw2)          -- 中间格缩放比
```
- **中间格平铺并缩放 sw/sh**，边缘行列保持原尺寸
- `cw < 1` 或 `ch < 1` ⇒ **`log.error` 并 `return nil`**（:712）
  ⇒ 必须保证 `out_w > tw1+tw3`、`out_h > th1+th3`

### ⚠⚠ 必须判返回值

`GG9View:new` 在**帧缺失**（:670）或**尺寸不足**（:712）时**返回 nil**，
后续 `:add_child` 直接崩。标准写法：

```lua
local bg

if frame_exists(PANEL_FRAME) then
	bg = GG9View:new(PANEL_FRAME, v(W, H), PANEL_SLICE)
end

if not bg then
	bg = KView:new(v(W, H))                       -- 兜底，不崩
	bg.colors = { background = { 30, 24, 16, 255 } }
end
```

现成用例：`kr1-desktop/data/kui_templates/map_counters_view.lua`
（`slice_rect=r(90,20,96,14)`）。

### ⭐⭐ slice_rect 必须照抄 KR6 自己的 kui_templates

**不能靠自己估**。猜错的后果：面板被切成**上下两截的平板**（实测踩过）。

索引脚本 `.workbuddy/_kr6_slice_index.py`：抓出全部
`(frame, size, slice_rect, 出处模板名)`。用法：

```bash
python .workbuddy/_kr6_slice_index.py | grep -i popup_bg
```

---

## 2. 字体：别名必须合法，且要防本体自带的坏映射

### 崩溃链（症状极具误导性）

```
all/gg_views.lua:214  attempt to index field 'font' (a nil value)
  ← GGLabel:get_wrap_lines → self.font:getWrap(...)
```
报错**只显示 font 是 nil**，看不出是字体名的问题。真线索在日志**另一行**：

```
font_db.error f() - Font title not found
```

### 根因（`lib/klove/font_db.lua:174-214`）

`font_db:f(alias, size)`：
1. 查 `self.fonts[alias.."-"..size]` 缓存
2. 查 `self.font_files[name]` —— 键是 `_assets/all-desktop/fonts/` 下的**真实文件名**
3. **两者皆无 ⇒ 只 `log.error("Font %s not found")` 然后 `return nil`**

alias → 文件名的映射来自 `all-desktop/data/font_subst.lua`。

### 合法别名白名单（= `font_subst.lua` 的全部键）

```
body  body_bold  body_slides  button  capitals  h  h_book  h_map  h_noti
h_popup  hero_name_label  hud  infobar_name  infobar_stats  sans  sans_bold
taunts  numbers  numbers_italic  numbers_bold
```

- **标题用 `h`**（本体 `GGPanelHeader` 就用它，`gg_views_custom.lua:356`）
- ⛔ 没有 `title`、没有 `body_light` 这类直觉名

### ⚠⚠ 本体自带缺陷：别名合法也会崩

`font_subst.lua` 里 `["zh-Hant"]` 的 `body_bold` / `h` 映射到
**`NotoSansCJKkr-Bold`，而 `fonts/` 目录里只有 `NotoSansCJKkr-Regular.otf`**
（已实证）⇒ 该语言下必崩。所以**不能只靠改字面量**，要加运行时守卫：

```lua
local FONT_FALLBACKS = { "body", "sans", "h", "taunts" }
local font_ok_cache = {}

local function font_usable(name)
	local cached = font_ok_cache[name]
	if cached ~= nil then return cached end

	local ok, F = pcall(require, "lib.klove.font_db")
	if not ok or not F then
		font_ok_cache[name] = true   -- 离线环境放行，不阻断构建
		return true
	end

	local ok2, font = pcall(F.f, F, name, 16)
	font_ok_cache[name] = ok2 and font ~= nil
	return font_ok_cache[name]
end

local function safe_font(name)
	if type(name) == "string" and font_usable(name) then return name end
	for i = 1, #FONT_FALLBACKS do
		if font_usable(FONT_FALLBACKS[i]) then return FONT_FALLBACKS[i] end
	end
	return "body"
end
```

**所有 `font_name` 赋值一律走 `safe_font`**，禁止裸字面量。

---

## 3. 点击：必须显式绑 `on_click` + 子视图放行传播

### 症状：面板能开、点不动 / 只有部分区域可点

### 机制（`lib/klove/kui.lua:1213-1222`）

```lua
for _, v in pairs(hl) do
	if v.on_click then
		self._click_start_view = v        -- 第一个带 on_click 的视图
		break
	elseif not v.propagate_on_click then
		break                             -- ⛔ 默认 false ⇒ 直接中断
	end
end
```

两条硬约束：
1. **可点视图必须"自身"有 `on_click`** —— `on_click` 是 KView 的**实例字段**
   （`kui.lua:553`），**类上不存在这个方法** ⇒ `HOOK(GGButton, "on_click")`
   会报"钩子加到不存在的函数"。
2. **遍历中遇 `propagate_on_click == false` 立刻 break**，而 `hit_all` 是
   **子视图先于父视图**（`kui.lua:746` 后序递归，自身最后压入）
   ⇒ 点在子 label / icon 上时**子视图先被命中**，子视图默认 `propagate_on_click`
   也是 false ⇒ 抢先 break，父视图收不到。

### 标准写法

```lua
-- 父：实例赋 on_click（本体范式，见 all-desktop/screen_map.lua:6702-6730）
row.on_click = function()
	room:add_spell(id)
end

-- 子：放行点击传播（GGButton 内部也是这么做的，gg_views.lua:580-582）
local function passthrough(child)
	child.propagate_on_click = true
	child.propagate_on_up = true
	child.propagate_on_down = true
end
```

⚠ 回调里捕获**局部 `room`**，不要用模块级 `M.room`
（`dismiss()` 后会被置 nil ⇒ 点崩）。

---

## 4. 按钮：`label_text` 必须是构造参数

```lua
-- all-desktop/gg_views_custom.lua:209
GGDoneButton.static.init_arg_names = {"label_text"}

function GGDoneButton:initialize(label_text)
	...
	if not self.label_text_key and label_text then
		self.label.text = label_text
	end
end
```

⛔ **构造后再赋 `.label_text` 完全无效**（只是个用不上的实例字段）⇒ 按钮上没字。

```lua
room.btn_confirm = GGDoneButton:new(tr("CONFIRM"))   -- ✅ 传进构造
room.btn_confirm.anchor = v(71.5, 35.5)
```

`GGDoneButton` / `GGKR1SelectButton` 的贴图**内置在类里**
（`heroroom_btnDone_large_0001` / `heroroom_selectBtn_0001`），不用外部传帧名。

---

## 5. 存档落盘：`all/storage.lua` 是单例，可直接用

`storage` 在 `screen_map.lua:20` 是**文件级 local**，看似拿不到；但
`all/storage.lua` 本身是**返回模块级单例表**的模块（`local storage = {}` …
末尾 `return storage`），而 Lua 的 `require` 对同一模块**缓存同一实例**
⇒ 插件里 `require("all.storage")` 拿到的就是本体那个 storage。

```lua
-- 本体范式：screen_map.lua:289 / 298 / 6849 …
storage:save_slot(user_data)
```

两条安全事实（`all/storage.lua:195/236`）：
- `save_slot` 是**整表序列化** ⇒ 加自定义键零成本
- `load_slot` 只校验 `SLOT_MANDATORY_KEYS` 的**存在性**、再补
  `SLOT_ADDITIONAL_DATA` ⇒ **没有删除未知字段的逻辑**，自定义键不会被读档清掉

⚠ 写盘要做 dirty 守卫 + pcall 吞错，**别每点一下就写**：

```lua
function M.flush()
	if not M._dirty then return false end
	local ud = M.get_user_data()
	if not ud then return false end

	local ok = pcall(function()
		require("all.storage"):save_slot(ud)
	end)

	if ok then M._dirty = nil end
	return ok
end
```

---

## 6. 其它 UI 硬规则（血泪清单）

### ⭐⭐⭐ 6.0 缩放素材只能用 `scale` —— `self.size` 对绘制无效

**这是最反直觉、最容易翻车的一条。**

```lua
-- lib/klove/kui.lua:665-668（KView:_draw_self 内）
local ss = self.image_ss
local ref_scale = ss.ref_scale * self.image_scale
G.draw(self.image, ss.quad, ss.trim[1]*ref_scale, ss.trim[2]*ref_scale, 0, ref_scale)
```

绘制尺寸 = **帧原生尺寸 × `ss.ref_scale` × `self.image_scale`** ——
**`self.size` 完全不参与绘制**。

而 `set_image(image, size)` 里的 `size` 只写 `self.size`（`kui.lua:518-536`），
它的作用只有两个：**命中判定** 和 **`anchor` 的基准**。

⇒ ⛔ **构造后赋 `.size = v(124, 123)` 是无效的**，素材仍按原生像素画出来
（症状：素材大一圈、压到别的东西上）。

两条正确路径：

| 路径 | 写法 | 效果 |
|---|---|---|
| `scale` | `view.scale = v(s, s)` | 缩放整个视图（含子视图与命中区） |
| `image_scale` | `KImageView:new(name, nil, s)` | 只缩放图像，不动 `size` |

⭐ **推荐用 `size.x` 反推缩放比**：`KImageView:new(name)` 不传 size 时，
`self.size` 自动 = 帧原生尺寸（图集 `ref_scale = 1` 时等于素材像素）
⇒ 图集重新生成后依然正确，**不用手抄数字**：

```lua
--- 把视图放进指定显示宽度（就地改 view 并返回它）
local function fit_width(view, target_w)
	local s = target_w / view.size.x

	view.anchor = v(view.size.x / 2, view.size.y / 2)
	view.scale = v(s, s)

	return view
end
```

⚠⚠ **换帧后必须重算**：`set_image(image)` 不带 size 时会把 `self.size`
**重置成新帧的原生尺寸**（`kui.lua:531-535`）⇒ 两个帧尺寸不同（如 157 vs 169）时，
不重算就会整体偏移：

```lua
if frame_exists(want) and view.image_name ~= want then
	view:set_image(want)
	fit_width(view, TARGET_W)      -- ⚠ 必须
end
```

---

### 6.1 其余硬规则

| 规则 | 说明 |
|---|---|
| `KView` 默认**全透明** | 槽位/卡片要显式 `colors.background`，否则肉眼看不见 |
| `KScrollList` **无 `item_height`** | `add_row(view)` 按 `view.size.y` 累加；清理用 **`clear_rows()`** 不是 `clear()` |
| **kui 的 Y 向下为正** | 实证 `view_to_screen`：`world_y = (y - anchor.y) * scale.y + pos.y`。写 `v(0, -20)` 会把元素推到**上方外面** |
| **九宫格是不透明板子** | 它必须 `add_child` 在 `KScrollList` **之前**（先加先绘），否则盖住列表内容 |
| 点击区域只认容器 `size` | 视觉元素比容器大时，容器要够大，否则只有一部分可点 |
| 关弹窗禁用 `destroy()` | 用 `hidden = true` + `parent:remove_child` |
| `GGLabel` **单行** | 塞多行必崩 |
| i18n 字段是 `current_locale` | 不是 `cur`（`all/i18n.lua:8`）；全局 `_("KEY", 默认值)` 缺键返回默认值 |
| `log` **不是全局** | 各文件自己 `require`；插件没有 log 实例时别写 `log.error`（会崩） |
| LuaJIT 2.1 = Lua 5.1 | **`table.pack` / `table.unpack` 都不存在** |
| 换帧前先 `frame_exists` | `KImageView:new(不存在的帧)` **不返回 nil**，而是在 set_image 抛错 ⇒ 随后 `kui.lua:529 attempt to index local 'ss'` |

### ⭐ 素材形状要先看，别按名字猜

**实测翻车**：`kr6_room_titlebar`（源帧 `room_tower_upgrade_9slice_popup_title_bg_rooms_`）
名字里带 `9slice` + `title_bg`，我当成"长条标题底"横拉 → 实际是 **306×177 的八角徽章**，
拉出来是个巨型八边形压住标题。

⇒ **动手前先把素材裁出来看一眼**（`magick dds:xxx.dds -crop ... +repage out.png`），
并确认它是"可拉伸的框"还是"固定形状的图"：

- 固定形状（徽章/图标/装饰）⇒ 只**等比缩放**，摆到合适位置
- 可拉伸框 ⇒ 才考虑 `GG9View`
- ⚠ 判断 `GG9View` 能不能用，看 slice_rect 是否合理：
  `r(102.9, -8.45, 9.75, 140.1)` 里 **th1 是负的、th2 高达 140.1**
  ⇒ 尺寸稍小就 `ch < 1` **直接返回 nil**，且拉出来必然变形 ⇒ **根本不该走九宫格**


### 挂载时机：绝不 `require` 大界面模块

⛔ **不要 `require("all-desktop/screen_map")`** 或 `MapView`（它就在 screen_map.lua
里）——其字段（如 `unlock_data`）在 **`init_coro` 协程体内**才赋值，mod 加载早于
游戏 GUI 定义 ⇒ 提前触碰崩 `screen_map.lua:2060 attempt to index field 'unlock_data'`。

✅ **惰性挂载**：HOOK 一个**必定存在**的每帧函数，每帧判目标就绪再挂。

```lua
HOOK(director, "update", function(next, self, dt)
	local updated = next(self, dt)      -- ⚠ 必须转发返回值，否则吞掉 updated
	pcall(M.try_install)                -- pcall 包住，挂失败不影响主循环
	return updated
end)
```

⚠ `director:update` **只在 `main.handler == director` 时被调用**（`main.lua:474
main.handler:update(dt)`）⇒ 建议**再加一道冗余触发**：等目标对象可见后 HOOK 它自己的每帧方法
（`screen_map:update`，`all-desktop/screen_map.lua:1229`）。本机已验证可用的参照插件
`reinforcement_system_reset` 就是这么做的（`HOOK(sm, "init"/"update"/"change_generation"/…)`）。

#### ⭐⭐⭐ 判"地图界面就绪"要用 `screen_map.window`，**不要**用 `main.screen_map_entered`

2026-10-16 实机踩坑（症状：**大地图上入口按钮不出现，且不报任何错**）：

- 曾用 `main.screen_map_entered`（`screen_map.lua:916` 在 `init` 末尾置真）当门槛
  ⇒ 实机诊断显示**该标志一直是 false** —— 人已站在大地图上、底部按钮条都在，
  入口却被这一条永远挡在门外。
- ✅ 正确判据 = **`screen_map.window`**（`screen_map.lua:319` init 里赋值、
  `:1224` destroy 里置 nil）⇒ 非 nil 即"地图界面已就绪、可挂按钮"。

#### ⚠⚠ `_G.screen_map` 可能是**被插件自己换掉的一张空表**

`screen_map.lua` 顶层写的是**全局赋值** `screen_map = {}`（`:51`）⇒
**任何一次 `require("screen_map")` 都会重跑该文件、把全局换成一张全新空表**；
引擎真正在用的那份（已 `init`、带 `window`）**只留在 `package.loaded` 里**。
⇒ 读 `rawget(_G,"screen_map")` 可能拿到"有表但 `.window` 恒 nil"的假对象。

**正确取法（只 peek，绝不 require）**：

```lua
local function pick_screen_map()
	local sm = rawget(_G, "screen_map")
	if sm and sm.window then return sm, "_G.screen_map" end
	-- 全局那份没有 window ⇒ 去 package.loaded 找带 window 的那份（只读，不触发加载）
	if type(package) == "table" and type(package.loaded) == "table" then
		local ks = {}
		for k, v in pairs(package.loaded) do
			if type(k) == "string" and k:find("screen_map", 1, true)
				and type(v) == "table" and v.window then ks[#ks + 1] = k end
		end
		table.sort(ks)
		if ks[1] then return package.loaded[ks[1]], ("package.loaded['%s']"):format(ks[1]) end
	end
	return sm, "_G.screen_map"
end
```

#### ⭐⭐ 入口按钮该挂在哪个坐标：用本体自己存的按钮引用，别扫 `children`

本体在 `screen_map:init` 末尾**存好了整条底部按钮条的引用**
（`all-desktop/screen_map.lua:919-923`）：

```lua
self._change_btn = change_button   -- 「切换地图」
self._u_btn / _e_btn / _a_btn / _h_btn
self.hero_but = h_button           -- :588 「英雄殿堂」
```

- 新按钮位置 = 取其中任一（如 `_change_btn`）的 `pos`，往前挪一档（本体档距 **170**）：
  `btn.pos = v(ref.pos.x - 170, ref.pos.y)`。
- ⛔ **不要用"遍历 `window.children` 挑最右 label 按钮"的启发式**：本体 `init` 是**分段落
  执行**（window 先建、按钮条后建），钩子落在中间时会挑到**错误按钮** ⇒ 入口错位，
  而且"已挂上"判定会变 true ⇒ **之后永不纠正**。
- 拿不到具名引用就**等下一帧**（每帧都重试），不要猜。

#### ⭐⭐ 挂载链必须留痕（否则"入口消失"只能靠猜）

挂载链上有多个静默 `return`（`GGButton` 全局没取到 / 参照点没就绪 / 图集帧守卫不过 /
标签配置抛错）—— 任何一处都会让入口**不出现且零日志**。做法（`kr6_powers` 已落地）：

- 写一个 `diag(msg, repeat_sec)`：**同时 `print` 到控制台 + 落盘** `kr6_room_diag.txt`
  （save 目录，走 `love.filesystem`，全程 `pcall`；不假定 `fs.append` 存在 → 读-拼-写兜底）。
- **同名状态隔几秒重报一次**（打印 `(xN)` 计数）——纯去重会让"状态一直不变"和
  "代码根本没跑"看起来一样；在大地图上只有**重复出现的等待行**才能证明"它一直在等"。
- 每个失败点给**带原因的**文案，成功时打 `OK: 入口已挂 pos=(x,y) 参照=… 标签=ok`
  ⇒ 坐标一眼看出是否画到屏外。
- **标签配置单独 `pcall` 且放在 `add_child` 之前**：`btn.label.*`（pos/size/text_size/
  font_size/fit_lines/text）任一字段在本体版本变动后失效都可能抛错，一抛整个 install
  就中断（还被外层 pcall 吞掉）⇒ 配不上最多"按钮没字"，绝不能让按钮挂不上。
- 遍历 `package.loaded` 找出所有含 `screen_map` 的键、打印各自有没有 `.window`
  ⇒ 一次性证实"读到的是不是引擎那份"。

#### ⚠⚠⚠ 本地函数必须**定义在使用点之前** —— 否则"功能全废且零日志"

**2026-10-16 血案（排错两小时）**：`M.install_entry_button` 的**第一行**就调用
`button_attached(sm, M.entry_button)` 做幂等保护，而 `local function button_attached`
当时写在**它后面**几百行处。

Lua 的 `local function f` 只在**其声明点之后**的词法作用域里可见 ⇒
`install_entry_button` 里的 `button_attached` 解析到的是**全局变量**
（`_G.button_attached == nil`）⇒ 调用即抛
`attempt to call global 'button_attached' (a nil value)` ⇒ 被外层
`pcall(M.try_install)` 吞掉 ⇒ **入口按钮永不安装，且一行日志都不打**。

**症状指纹（记住它，能省两小时）**：
- diag 能正常打出"更早一步"的日志（如 `就绪: 拿到地图窗口 … 已挂=false`），
  但**该函数内部的任何 diag 都不出现** —— 说明调用在**进入函数体之前**就崩了，
  或被调函数在**第一条语句**上崩了。
- 于是"最外层 pcall 吞错 + 更早的日志反复重播"= 前向引用/首行崩溃的典型特征。

**规矩**：
1. 插件文件里凡被 `M.xxx = function` 引用的 `local function`，**一律排在第一个使用点之前**；
   写"工具函数区"就统一放文件**顶部**（`local M = {}` 之后）。
2. **这类错是合法语法** ⇒ 语法检查、文本 grep、甚至"函数存在性"断言都抓不到。
   ⇒ 必须在探针里断言**位置关系**（用 `src:find` 返回的下标比大小）：
   ```lua
   local i_def = code:find('local%s+function%s+button_attached')
   local i_use = code:find('function%s+M%.install_entry_button')
   assert(i_def and i_use and i_def < i_use)
   ```
   ⚠ 只对**真正被引用的** local 这样断言；没被引用的（如只在别处用的
   `pick_screen_map`）应改断言"定义 < 它自己的使用点"，否则会误报。

---

## 7. 复用 KR6(Genesis) 原版图集素材

### 素材位置（唯一正确来源）

```
Kingdom Rush Genesis/Kingdom Rush Genesis/_assets/kr6-desktop/images/fullhd_bc3/
├── gui_common.lua      + gui_common-1.dds        （1082 帧：通用 UI）
├── gui_popups.lua      + gui_popups-1.dds        （弹窗底板家族）
├── room_tower.lua      + ...-1.dds               （法术/塔房间，含法术槽位框）
├── room_upgrades.lua                              （升级房，含标题条）
├── room_hero.lua / room_item.lua / room_level_select.lua
└── room_common.lua                                （房间背景插图）
```

⚠ **另一 packing（`_ov` / demo 的索引）quad 全对不上** —— 必须用这个目录。
`.dds` 用 ImageMagick 按 `f_quad` 裁剪即可（`magick dds:xxx.dds -crop WxH+X+Y`）。

### 已实证可用的一批帧

| 用途 | KR6 帧 | slice_rect |
|---|---|---|
| 面板底板 | `UI_settings_9slice_popup_bg_` (195×598) | `r(57.6, 84.35, 22.8, 226.75)` |
| 法术名册底 | `room_tower_9slice_rooms_desktop_roster_bg_` (114×107) | `r(20, 18.95, 40.15, 37.95)` |
| 标题条 | `room_tower_upgrade_9slice_popup_title_bg_rooms_` (306×177) | 整块缩放 |
| **法术槽位框**（空/选中/已获得） | `room_tower_image_power_lvl_bg_0001` / `_bg_0003` / `_frame_aqcuired_1_` | 整块 |
| 槽位阴影 | `room_tower_image_power_lvl_bg_shadow_` | 整块 |
| 通用按钮框 | `ingame_ui_items_button_frame` 家族 | — |

**槽位模板范例**：`kr6/data/kui_templates/button_power_upgrade_slot_1.lua`
（KR6 自己怎么用这批槽位素材，直接照抄）。

### 生成插件图集

`_gen_kr6_room_atlas.py` 的做法（可套用到任何一批素材）：
1. 从 KR6 索引 + dds 裁出每个帧 → PIL Image
2. 简单行式紧凑排布（超宽换行），拼成一张 PNG
3. 写 KRAB 风格 lua 索引，**关键约定**：
   - `trim` 全 0、`size` == `f_quad` 宽高 ⇒ **逻辑坐标 == 素材像素**
   - `a_size` = 图集总尺寸
   - 帧名统一加独立前缀（如 `kr6_room_`）防撞本体 `db_atlas` 全局键空间
4. 插件入口 `ATLAS_NAMES` 加进清单，图集以 `ref_scale = 1` 加载
   ⇒ **KR6 的 slice_rect 原值可直接用**（KR6 帧无 baked ref_scale）

⚠ 抽取器正则**别写 `[a-zA-Z0-9_ ]+`** —— 会把 `= ` 前的空格贪婪吃进捕获组，
键名带尾空格 ⇒ 全部 MISS。用 `([a-zA-Z0-9_]+)\s*=\s*\{`。

⚠ **新图集文件必须连 PNG + lua 一起推到 AppData**（漏推 ⇒ Image not found 连锁）。

---

## 8. ⭐ 离线出图工作流（本技能最有价值的部分）

面板改版只能靠用户截图反馈，一轮来回很贵。**用 PIL 重实现 GG9View 算法**，
在 Python 里把成品渲染出来，自己先看。

### ⭐⭐⭐ 铁律：预览必须复现引擎的**真实绘制语义**

**实测翻车**：第一版预览按"目标尺寸"贴图（`sc(frame, 124, 123)`），
而引擎实际是"**原生尺寸 × `scale`**"画（见 §6.0）⇒ **预览看着对，游戏里框大一圈**。
用户截图才发现。

⇒ 预览里的每个元素都要按引擎的算法画。对照表：

| 引擎里的写法 | 预览里该怎么画 |
|---|---|
| `KImageView:new(f)`（不传 size） | 原生尺寸 |
| `fit_width(view, w)` → `scale = w/size.x` | `原生尺寸 × (w / 原生宽)` |
| `GG9View:new(f, size, slice)` | 九宫格平铺算法（下） |
| `view.hidden = true` | 不画 |

```python
def fit(frame, target_w):
    im = sprite(frame)
    s = target_w / im.width
    return im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
```

### GG9View 的算法复刻

```python
# 严格照抄 all/gg_views.lua:703-745
tw1, tw2, tw3 = L, W, iw - (L + W)
th1, th2, th3 = T, H, ih - (T + H)
cw = round((out_w - tw1 - tw3) / tw2)
ch = round((out_h - th1 - th3) / th2)
sw = (out_w - tw1 - tw3) / (cw * tw2)
sh = (out_h - th1 - th3) / (ch * th2)
# 中间格平铺并 resize 到 (dw, dh)，边缘行列保持原尺寸
```

参考实现：`.workbuddy/_kr6_room_mock2.py`（合成整屏预览）、
`.workbuddy/_kr6_panel_preview.py`（多候选对比图）。

> 本技能包 `scripts/` 下已归档这 5 个脚本，可直接复制进新项目的 `.workbuddy/` 使用。
> ⚠ 里面的 `GEN` / `DST` / `MAGICK` 路径是硬编码的本机绝对路径，用前要改。

⚠ **别用 ImageMagick 逐格 `-composite` 拼**（命令行会超 Win32 长度上限，
报 `WinError 206 文件名或扩展名太长`）——用 PIL 在内存里拼。

### 布局几何自检

`.workbuddy/_kr6_room_layout2.py`：把 room 的**显式坐标常量**复刻成 Python，
算出每个元素矩形，输出：

1. **出界检查** —— 有没有元素超出面板
2. **主要块重叠检查** —— ⭐ **装饰层要从检查里排除**：标题条压标题文字、
   阴影压框底都是**设计意图**，不是 bug
3. **容器内越界检查** —— 子元素有没有超出父容器（槽位框超出槽位容器 = 真 bug，
   会导致部分区域点不到）
4. **示意图** —— 画出来自己看一眼

**改布局先跑它**，能抓出真问题（实测抓到：槽位框超出容器、列表小标题压住列表顶边）。

---

## 9. 收尾 checklist

```bash
# 1. 语法
python .workbuddy/lua_syntax_check.py mods/local/<插件>/*.lua

# 2. 布局自检（改了坐标才需要）
python .workbuddy/_kr6_room_layout2.py

# 3. 离线预览图
python .workbuddy/_kr6_room_mock2.py _preview.png

# 4. 探针（静态断言：帧名合法 / 字体白名单 / on_click 都绑了 / 图集清单含新图集）
python .workbuddy/run_lua.py KingdomRushDove .workbuddy/verify_<插件>_room_static.lua

# 5. 双侧同步（⚠ 新图集文件要连 PNG+lua 一起推）
python .workbuddy/compare_plugin_sync.py <插件> --dev mods/local/<插件> --app "$APPDATA/LOVE/kingdom_rush_dove/plugins/<插件>"
```

探针该断言什么（`verify_kr6_room_static.lua` 的结构可直接抄）：
- ⛔ 不 require screen_map / MapView
- ⛔ 不 HOOK 不存在的类方法（`GGButton.on_click`）
- ⛔ 不用 `table.pack` / `table.unpack` / `item_height` / `list:clear()` /
  `i18n.cur` / 裸 `log.`
- ⛔ 剥注释后再检查（否则"注释里写的反面例子"会被自己命中，产生假 FAIL）
- ✅ 所有 `font_name` 取值都在 `font_subst` 白名单内 **且都走 safe_font**
- ✅ 槽位 / 列表行 / 按钮**都绑了 `on_click`**；子视图放行传播的数量 ≥ N
- ✅ 九宫格：`GG9View` 存在、`slice_rect` 用 `r(...)`、**返回值判 nil**
- ✅ 图集清单含新图集名，且索引文件在磁盘上、含预期帧名
- ✅ ⭐ **缩放走 `fit_width`（scale），禁止 `xxx.size = ` 这类"假缩放"写法**
- ✅ ⭐ `set_image` 换帧后有重算 `fit_width`（`set_image` 会重置 `self.size`）

## ⭐⭐⭐ 同一族框帧换图必须**连 pos 一起换**（2026-10-17 kr6_powers 按钮图标"变小没充满"血案）

### 症状
玩家反馈「选中法术时图标变小了、没充满外框、位置偏右上」。常态看着正常。

### 真因
按钮框按状态换帧（`items_frame` ↔ `items_frame_select`），但**两个帧不是同尺寸**：

| 帧 | quad | size(逻辑) | 可见内腔 | 内腔中心(视图坐标) |
|---|---|---|---|---|
| `kr6_ui_items_frame` | 119×133 | 155×172 | 89×100 | (77.0, 83.5) |
| `kr6_ui_items_frame_select` | 135×144 | 169×177 | 84×78 | (84.5, 77.5) |

共用同一个 `mask.pos` ⇒ 选中瞬间框整体跳 (+7.5, −6)。
更反直觉的是：**select 帧视觉更大（169 > 155）但内腔更小（84×78 < 89×100）** ——
它的边框/装饰更厚，所以图标被吃掉一圈 ⇒ 观感"图标变小"。

### ✅ 修法
每个状态各算一个 pos，基准都取**内腔中心对齐**（不是视图中心）：

```lua
local BASE_IN_X, BASE_IN_Y = -16.5, -63        -- 常态：历史定版值，别动
local CAV_DX, CAV_DY = 7.5, -6                 -- select内腔中心 − normal内腔中心
local BASE_SEL_X = BASE_IN_X - CAV_DX
local BASE_SEL_Y = BASE_IN_Y - CAV_DY
-- 再统一减图标偏移补偿（/BTN_SCALE），保证改 ICON_OFF 时两态一起走
```

### ⭐ 量内腔的正确方法（别量视图中心）
```python
# ① 从图集裁 quad；② 取中心行/列的 alpha；③ 找**最长连续 alpha<200 段** = 内腔
def longest_tr(line):
    best=(0,-1); cur=None
    for i,v in enumerate(line):
        if v<200:
            if cur is None: cur=i
            if i-cur > best[1]-best[0]: best=(cur,i)
        else: cur=None
    return best
# ④ 内腔中心(视图坐标) = (内腔中点 + trim[0/1])
```
- ⚠ **不要用 min/max 取全部透明像素**：中心线会穿过边框，min/max 会退化成 `(0, w-1)`（我第一版就是这么错的）。
- ⚠ **视图中心 ≠ 内腔中心**：两者最多能差 11px（select 帧），差这么多必然错位。

### 离线复刻的必踩坑：**composite 时必须加 trim 偏移**
```python
# kui 绘制：G.draw(img, quad, trim[1]*ref, trim[2]*ref, 0, ref)
# ⇒ quad 贴到父坐标的位置 = view.pos + trim，不是 view.pos
cv.alpha_composite(frame, (mask[0] + trim[0], mask[1] + trim[1]))   # ✅
cv.alpha_composite(frame, (mask[0], mask[1]))                        # ❌ 整体偏一个 trim
```
漏了这个偏移，复刻图会显示"图标溢出框外"，让人误判成尺寸问题、白查半小时。

### 探针要加的断言
1. `set_mode` 的 `selected` 分支用**独立的** pos 常量（正则查 `v(MASK_X_SEL, MASK_Y_SEL)`）。
2. 常态分支仍用原常量（防"顺手把常态一起改了"，那是用户已认可的位置）。
3. **数值自洽**：按同一公式算出两态的"内腔中心落点"，都必须落在图标中心 ±2px。
4. 负向自测：把 select 分支改回共用 pos ⇒ 必须精确报 FAIL。

## ⭐⭐⭐ `db_atlas` 是全局单表，键=帧名 —— **别的插件会抢你的帧**（2026-10-17 kr6_powers 图标缩一半血案）

### 症状
图标显示只有设计尺寸的一半、缩在外框左上角；框本身正常。**本体更新前正常，更新后变这样。**

### 判据（一眼定位）
同一父视图下，子视图（框）和本体（图标）的**相对比例失衡**。
`scale` / `size` 都继承父链，父链一致时比例不可能变 ⇒ **只可能是两者的 `ref_scale` 不同**。
量法：玩家截图里量两者像素，除以设计 quad：
```
图标 42/105 = 0.40    框 97/119 = 0.82     ⇒ 相差 2 倍 ⇒ ref_scale 不一致
```

### 真因
`image_db.db_atlas[frame_name]` 是**全局单表**，load_atlas 时按帧名写入，**后加载者覆盖先加载者**。
本例：用户的「资源」插件自带 KR6 `gui_common` 图集，里面有**同名** `in_game_icon_power_*`，
以另一套 ref_scale 加载 ⇒ 覆盖了插件的同名帧 ⇒ 图标按别人的比例渲染。**框帧名是插件独有的，所以没被抢**。

### ✅ 铁律：插件自用素材**不得直接沿用原版帧名**
```lua
-- ❌ 会把命交给加载顺序
icon = "in_game_icon_power_rain_of_fire"
-- ✅ 独占前缀（本项目 kr6p_），任何插件都猜不到
icon = "kr6p_in_game_icon_power_rain_of_fire"
```
- 图集 lua 里的**键**和代码里的**引用**必须同步改（两处漏一处 = 图标消失，不是变小）。
- PNG 不用动（帧名只是索引键）。
- 别名（`alias`）指向的帧也要一起改。

### ⚠ 排查误区
- **别以为冲突源一定是本体**。本体 grep 干净 ≠ 安全，`mods/local/` 下**任意**插件都可能是凶。
  正确做法：**全库 grep 帧名 → 看有几个文件定义它**：
  ```bash
  grep -rl "in_game_icon_power_rain_of_fire" --include=*.lua .
  ```
- **离线 PIL 复刻验证不了这件事**：复刻只证明"设计自洽"，证明不了运行时 `db_atlas` 被谁覆盖。
  比例失衡类问题**必须拿玩家截图量像素**，别只信复刻（我这次就因此走了两小时弯路）。

### 探针
1. 图集里目标帧**全部**带独占前缀（数键数，且裸名计数为 0）。
2. 代码里不再出现裸帧名字符串（逐行扫，允许注释）。
3. 运行期取到的 `def.icon` / `def.frame` 全部匹配 `^<prefix>`。

## ⭐⭐ 借用本体帧当图标 —— **尺寸/trim 天然不同**，会显小还偏移（2026-10-18 迪纳斯）

### 症状
某个图标在按钮里**明显比别人小一圈、还缩在右下角**。不是被抢帧（帧确实解析到了）。

### 判据
同一父视图下，图标比别人小且偏 ⇒ 读它的真实参数：
| 帧 | 逻辑 size | 绘制 quad | trim |
|---|---|---|---|
| 自家图标 | 108×108 | **105×106** | (2,1) |
| 本体头像 `kr3_hero_portraits_0005` | 144×142 | **83×83** | **(30,24)** |

绘制是 `G.draw(img, quad, trim[1]*ref, trim[2]*ref, 0, ref)`：
**实际画的是 quad 尺寸**，`trim` 是视图内偏移。所以逻辑 size 一样（108 vs 144 看着都"一格子"）
不代表画出来一样大。

### 离线拿 KRAB 帧的真实 quad（love_stub 读不到，直接解析 .bin）
```python
p = 5                                   # magic 'KRAB'(4) + version(1)
frame_count = <I; name_count = <H
for _ in range(name_count): <H len; skip bytes        # 图集名
for _ in range(frame_count):
    <H name_len; name
    a_idx = <H                          # ⚠ 这 2 字节**含在**下面 18 里
    f_quad(4H) a_size(2H) trim(2H)      # 共 16 字节
    ref_scale = <f                      # 4 字节
    p += 22                             # ⚠ 不是 2+18
    size_x, size_y, alias_count = 3H
    ... alias 列表
```
`trim` 在 KRAB 里只有 2 个值（x,y），`size` 存在后面的 3H 里。

### ✅ 修法：搬进自家图集，做成**标准尺寸**帧
1. 从本体 dds 裁下 quad（PIL 直接能读 .dds）
2. 缩放到与自家图标**相同的 quad 尺寸**（本例 105×105）
3. 按自家图标的视觉风格处理（圆角 + 描边），否则直角照片贴在圆角图标里很突兀
4. 扩图集 PNG（向下加一行最省事，旧帧 f_quad 全不用动），**所有帧的 `a_size` 一起改**
5. 代码引用改成新帧名

### ⚠⚠ 图集改动三查（缺一个就花屏/错位）
```python
# ① 每帧 a_size == PNG 实际尺寸
# ② 每帧 f_quad 不越界（x+w<=W, y+h<=H）
# ③ size.x-trim_l-trim_r == quad_w 且 size.y-trim_t-trim_b == quad_h
```
⛔ **PNG 与 lua 必须同时更新**：只改 lua 会指向不存在的区域；只改 PNG 则新帧取不到。

### ⭐ 顺带的好处
图标全部来自自家图集后，探针里"允许本体帧"的白名单就可以**清空**，
统一要求 `^kr6p_` 前缀 —— 顺带把「被别的插件抢帧」的隐患也堵死了。

### ⭐⭐⭐ 「裸美术图标」要补底板，`trim` 必须归零（2026-10-20 龙息法杖）

**症状**：从别的版本抽来的图标（商店图标 / 背包图标）挂进 KR6 按钮框里，
**四周全透明、像一根悬空的物件**，和同排 10 个图标完全不是一套（用户原话：「图标需要一个背景框」）。

**判据**：看图标帧的 `bbox`。KR6 自家的 9 个法术图标都是**满幅**（108 画布、内容 105×106），
底图是画进美术里的（径向辉光 + 放射光束 + 2px 深色描边，每个图标一套配色）。
裸美术 bbox 通常只有中间一块 ⇒ 缺的是**底板**，不是框（框由 `kr6_ui_items_frame` 提供，所有按钮都有）。

**做法**（`.workbuddy/gen_drf_icon_plate.py`，PIL + numpy 程序化生成 108×108）：
```python
# ① 径向渐变：中心亮青 → 饱和蓝 → 四角深青（t = r / 半对角线，0..1）
STOPS = [(0.00,(188,252,255)), (0.16,(126,234,255)), (0.32,(40,188,246)),
         (0.50,(0,142,214)), (0.70,(0,100,164)), (0.86,(2,66,110)), (1.00,(3,40,70))]
# ② 16 束放射光：clip(cos(16θ),0,1)**2.2 * falloff(中段才亮) * 0.11 → 白，alpha 混合
# ③ 2px 深色描边 (4,32,56)
# ④ 裸美术等比缩到 ~100px 高、居中 paste（alpha_composite）
```
- ⚠ **`trim` 必须改成 `{0,0,0,0}`**：`kui.lua:668` 是
  `G.draw(img, quad, trim[1]*ref, trim[2]*ref, 0, ref)` ⇒ trim 的前两个数是**绘制偏移**。
  补了底板后内容满幅，还留原来的 `(12,1)` 会把整张图**右移 12px、下移 1px**。
- ⚠ **合成脚本要幂等**：底板 + 裸美术再合一遍就套娃。第一次运行时把裸美术另存成缓存
  （`_drf_icon_bare.png`），之后一律从缓存合；并加一道「四角不透明 = 已加过底板」的拒绝。
- 视觉验收：把新图标与 2~3 个兄弟图标拼成 1× + 3× 对照图，**先看图再接进游戏**；
  再按框内腔（89×100）裁一刀模拟遮挡，确认裁掉边框后仍有完整背景。
- 美术来源参考：KR3 背包道具的**原版框**是 `backPack_icons_0001`（青绿圆珠），
  `backPack_icons_0002` 是放在它上面的道具美术（`GameItemButton` 里 scale 0.7 + pos(-2,-2)）
  —— 想还原「原版背包里的样子」就照这个合成，但它是圆形、四角仍是透明，塞方框里会显小。

---

## ⭐⭐⭐ `KScrollList` 的 `drag_scroll_threshold` 默认 0 —— 会吞点击（2026-10-18 实测）

`lib/klove/kui.lua:2100` 的 `KScrollList:update`：

```lua
if any_button_down and self._down_y then
	local a = wy - self._down_y
	if math.abs(a) <= self.drag_scroll_threshold then
		return            -- 阈值内：不滚动，普通点击
	end
	...                    -- 超过阈值：进入拖拽滚动
```

`initialize` 里 **`drag_scroll_threshold = 0`**。于是 `math.abs(a) <= 0` 只在**完全没动**时成立 ——
真人点一下必然有 1~3px 抖动 ⇒ 被判定为拖拽 ⇒ **`on_click` 被吞**。
表现：**列表行点不动 / 槽位取不下来 / ± 按钮没反应**，且零日志。

```lua
local list = KScrollList:new(v(LIST_W, LIST_H))
list.drag_scroll_threshold = 10        -- ⭐ 必须显式设 > 0
list.scroll_amount = 60
list.propagate_on_click = true
list.propagate_on_touch_down = true    -- 安卓拖动滚动
list.propagate_on_touch_up = true
```

⚠ **什么情况下这个 bug 会暴露**：列表内容超过可视高度（需要滚动）时最明显；
  内容不满一屏时 `_bottom_y <= size.y`，`on_down` 直接 return ⇒ 看起来一切正常。
  ⇒ **候选/条目一多就"突然点不动"**，别往别处找。

## ⭐⭐ 卡片网格容量自检（加法术/条目时提前发现溢出）

网格页（如 `kr6_powers_settings_ui` 的法术卡片）几何是硬编码常量，
加一个条目就可能溢出/需要滚动。把**容量检查写成断言**而不是靠肉眼：

```lua
-- 从源码读常量（注意是多变量声明 `local PW, PH = 920, 752`，且行尾有中文注释）
local clean = src:gsub('%-%-[^\n]*', '')            -- 先去注释，否则匹配不到行尾
for names, vals in clean:gmatch('local%s+([%w_,%s]-)%s*=%s*([%d%s,%.-]+)') do ... end

local rows = math.ceil(#S.SPELLS / CARD_COLS)
assert(rows * (CARD_H + CARD_GAP_Y) <= list_h)      -- 总高 ≤ 列表高
assert(#S.SPELLS <= math.floor(list_h / (CARD_H + CARD_GAP_Y)) * CARD_COLS)
```

本例实测：面板 920×752 / 列表 880×618 / 卡片 262×108 三列 ⇒ **8 个法术 3 行 = 366px**，
最多能放 15 个不滚动 —— 空间很宽裕，但断言留着，第 16 个时会自己报红。
