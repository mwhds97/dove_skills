---
name: kr-dove-tavern-add-unit
description: 给《王国保卫战Dove》招募酒馆 mod（mercenary_tavern）新增召唤单位的完整 checklist：注册链路 7 触点、近战/远程模板骨架选择、属性面板三坑、克隆多段攻击敌人的崩溃坑、贴图动画验证、伤害叠层等自定义机制实现范式。当用户说"酒馆加单位/新增召唤单位/把XX敌人改成友军"时使用。
agent_created: true
---

# 酒馆新增召唤单位 Checklist

工作副本：`KingdomRushDove/mods/local/mercenary_tavern/`（用户惯例：只改这份，AppData 用户自己同步）。

## 注册链路（7 个触点，缺一即崩或不可见）

| 文件 | 改什么 |
|---|---|
| `balance.lua` | 末尾追加 `xxx_cost = cfg.xxx_cost or N` + `xxx = {...}` 数值段（`max_speed = (cfg.xxx_max_speed or v) * FPS`） |
| `mercenary_tavern_templates.lua` | ① 酒馆塔 `attacks.list[N+1]`（price + action_id="summon_xxx"，N=现有最后一段）② i18n 段（`SUMMON_XXX(_DESCRIPTION)` + `_NAME_NAME` 键，见坑3）③ 文件尾 `return {}` 前加单位模板 |
| `mercenary_tavern_scripts.lua` | ① `tower_mercenary_tavern.update` 协程里加 `elseif this.user_selection.arg == N+1` 分支（扣费→create_entity→powers 继承→soldier_inherit_tower_buff_factor→apply_hero_auto_rally_config→insert+双 signal）② 文件尾 `return {}` 前加 `scripts.xxx_reinforcement` |
| `mercenary_tavern_menu.lua` | 召唤按钮（`action_arg=N+1`、`place=递增`、image 用敌方原 portrait）+ buttons 表尾插入 |
| `mercenary_tavern_config.lua` | 默认键（尾部 chronological 区）+ key_label_map 中文标签 |
| `config.lua` | version bump |
| `readme.md` | 召唤列表加一行 + 版本历史（新单位只在"列表+版本历史"记，不写详情段） |

arg 编号 = attacks.list 序号（面板/菜单/脚本三处必须同号）。语法校验：`.workbuddy/lua_syntax_check.py`。

**描述格式（用户约定）**：按钮 tooltip 用标准短句 `花费%d金币在路径上召唤XX，持续一整局。`，不堆机制细节——机制说明放属性面板 get_info 的 `special` 字段（如 executioner 的充能说明、blazefang 的叠层说明）。

## 骨架选择（照抄现有脚本）

- **纯近战**：orc_reinforcement（最简，`y_soldier_melee_block_and_attacks`）
- **近战+远程混合**：shadow_archer_reinforcement（`y_soldier_ranged_attacks` 优先，无目标/冷却转近战）
- 永续协程骨架 + `goto label_end` 照抄；模板 AC 行照抄 orc。

## 面板三坑（都踩过）

1. **远程行显示"无"**：面板 `game_gui.lua:3172` 读 `ranged.attacks[1]` **本体**的 damage_min/max —— 必须在模板给攻击本体挂伤害值（真实伤害走子弹模板，两处都设）。
2. **get_info 必须带 `ranged_cooldown`**，否则远程行只有数字没间隔。
3. **面板标题** = `_(info.i18n_key .. "_NAME")`（game_gui.lua:2997）。i18n_key 若带 `_NAME` 后缀，必须同时定义 `_NAME_NAME` 键（jack/螃蟹/弓手先例）。

## 克隆敌方模板的坑

- **多段攻击敌人**：克隆前检查敌方 `ranged.attacks[2..n]` / `timed_attacks`。blazefang 的 `attacks[2]` 是 20% 即死弹 deepclone、无 per-attack cooldown（敌方用组件级 `ranged.cooldown`）→ 友军选攻击时 `a.cooldown * factor` 对 nil 算术崩（script_utils.lua:1739）。删法：`xxx_t.ranged.attacks[2] = nil`。
- **death_spawns 自爆**（如 blazefang_explosion）会误伤友军 → `death_spawns = nil`（恶魔军团先例）；`explode_when_silenced_death = false`。
- 水栖敌人：`enemy = nil` 移除 valid_terrains + `water = nil`，按陆地单位做（nav_grid 不支持水面寻路）。
- 扫描脚本（判断所有基底是否有 attacks[2]）：见 2026-09-29 memory 或用正则扫 `kr1/enemies.lua` 各 RT 块内的 `ranged\.attacks\[2\]`。

## 贴图/动画验证

用 `kr-dove-enemy-data` 技能的"动画键与贴图组验证"节：`kr1/data/game_animations.luac` 提 `{prefix}_*` 键（需 walk×3/idle/attack[/shoot/ranged_*]），帧名反查图集组，确认组在 `mercenary_tavern.lua` 的 required_textures/load_texture_groups 列表（`go_enemies_common` 是默认组不用加）。

## 删除单位（逆向摘除 7 触点，2026-09-29 blazefang 实操）

7 触点同新增表反向删：balance 数值段（`blazefang_cost` 行 + `blazefang = {...}` 整块）→ templates（list[N] 3 行 + i18n 3 行 + 文件尾模板/子弹块，注意保留同区其他单位的块）→ scripts（arg==N 分支 + 文件尾 scripts.xxx_reinforcement / 自定义子弹脚本块）→ menu（按钮定义 + buttons 表项）→ config 键与 key_label_map 标签（**按行过滤 `xxx_` 即可，标签/键都是独立整行**）→ 版本 bump → readme 加"移除"版本段（历史记录保留）。

**删 elseif 分支的大坑（踩过，误删 2000 行）**：末位分支（链里最后一个 `elseif`）后面跟的是链闭合 `end` 而不是下一个 `elseif`。用「找下一个 elseif 定位结束」会把分支之后到几千行外某个 elseif 之间的所有无关代码全删掉。**正确定位：从分支开头删到下一个 `\n\t\t\tend\n`（3-tab end，保留该行作链闭合）**。任何切片删除后必须：① `assert "xxx" not in content.lower()` ② 重新 grep 全部单位脚本块还在（`grep -c "scripts\..*_reinforcement = {}"`）③ 语法校验。

**误删恢复源**：本机无 git 时，`%APPDATA%/LOVE/kingdom_rush_dove/plugins/<插件名>/` 通常是用户同步过的完整旧版本，cp 回来重做即可。改完提醒用户重新同步 AppData（AppData 里还是含被删单位的旧版）。

## 自定义机制范式（伤害叠层等）

用 `bullet.damage_hooks`：hook 签名 `(entity, damage, protection)`（utils.lua:2027），真实结算走 `U.predict_damage`（systems/health.lua:675），**mutate damage.value 即生效**（hooks 在 dvalue 读取之前）。无 store 参数 → 逐目标状态挂**目标实体**字段；加 `damage._tag` 一次性标记防狼人 on_damage 预判双触发。参考 `scripts.bolt_blazefang_friendly.amp_hook`（注意：blazefang 已于 v0.3.11/v1.3.1 从两插件删除，此参考仅存于 readme 历史与 git 外备份）。

## 收尾

config 版本 bump、readme 版本历史、5 文件语法校验全过、提醒用户同步 AppData（若游戏已写回旧 config 值，覆盖同步才生效）。
