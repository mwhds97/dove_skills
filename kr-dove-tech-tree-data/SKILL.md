---
name: kr-dove-tech-tree-data
description: 查《王国保卫战 Dove》四棵本体科技树里每个天赋的 key、中文名（i18n）、等级/价格/图标，以及"同一位置在不同科技树里是不同 key"这类分歧的核对方法。当需要"某科技叫什么名字""第 N 级科技对应哪个 key""插件面板名字和游戏里对不上""某个科技为什么改不动"时使用。
agent_created: true
---

# KR Dove 科技树数据核对

适用：给科技做名字对齐、写科技类插件（改数值/加开关）、排查"面板显示的名字和游戏里不一致"或"某个科技改了没反应"。

## 核心结论（先看这条，能省一次误判）

**同一个"第 N 级科技"在不同科技树里可能不是同一个 key，名字也不同。** 只按等级/名字推断必然出错。

已核实的分歧点（v2.0.3.x）：

| 位置 | 科技三（`list_id = 3`） | 科技四（`list_id = 4`） |
|---|---|---|
| 雷暴最高级 | `thunder_level_6` = **艾纳尼祝福**（改 `main_script.insert`：闪电瞬间复活全部士兵） | `thunder_typhoon` = **洗礼**（主/副闪电各 10 发、`slow.factor = 0.25`、`extra_duration = 4`） |
| 雷暴 1~5 级 | `thunder_level_1..5` | 同名同 key |
| 援军 1~6 级 | `reinforcement_level_1..6` | 同名同 key（四棵树通用） |
| 火雨 | `rain_*` | 同名同 key（四棵树通用，但数值不同，**不可跨树累加**） |

**全部火雨 + 雷暴项的 `class` 都是 `"rain"`**：`rain_blazing_skies` / `rain_scorched_earth` / `rain_bigger_and_meaner` / `rain_blazing_earth` / `rain_cataclysm` / `rain_armaggedon`，以及 `thunder_level_1..6` / `thunder_typhoon`。判断"本体点没点"只用 `levels.rain`。

科技四独有的新增项：`mage_rune_analysis`、`mage_purge_field`、`engineer_emergency_expansion`、`archer_fly_killer`、`barrack_skill_master`、`mage_harmony`、`thunder_typhoon`。

## 本体技能跟着科技树变（改联动/技能类功能必看）

`kr1/upgrades.lua:2379-2383`：

```lua
if self.list_id == 1 or self.list_id == 2 then
    E:set_template("user_power_1", T("power_fireball_control"))   -- 科技一/二：技能一 = 火雨
elseif self.list_id == 3 or self.list_id == 4 then
    E:set_template("user_power_1", T("power_thunder_control"))    -- 科技三/四：技能一 = 雷暴
end
```

含义：**同一个"技能一"在不同科技树下是两个完全不同的模板**。做联动、改冷却、改效果时，只处理其中一个模板就只覆盖一半玩家。

- 技能等级：火雨读 `upgrades.levels.rain`（`upgrades.lua:2385`，有值）；雷暴那行写的是 `self.levels.thunder`（`upgrades.lua:2437`）—— **`levels.thunder` 根本不存在**，永远是 nil，别拿它当雷暴等级用。
- ⭐ **雷暴天赋的 `class` 也是 `"rain"`，不是 `"thunder"`**（`upgrades.lua` 里 `thunder_level_1..6` 与 `thunder_typhoon` 全部写 `class = "rain"`）。存档 `slot_N.lua` 的 `upgrades` 表只有 `archers / barracks / mages / engineers / rain / reinforcements` 六项。⇒ **火雨与雷暴共用 `levels.rain`**，判断"玩家点没点法术科技"只能看 `levels.rain`，拆不开。
- ⭐ 由此推论：**原版雷暴天赋本身就不校验等级**——`upgrades:get_upgrade` 里 `u.level <= self.levels[u.class]` 遇到 `class="rain"` 是能比的，所以雷暴 1~6 级确实被 `levels.rain` 卡；但 `upgrades.lua:2440` 那句 `self.levels.thunder = nil` 让凡是跨树合并/忽略等级的实现都会把雷暴全放开。写插件时若要"随本体科技"，判据一律用 `levels.rain`，**不要**去找 `levels.thunder`（会恒 false，把雷暴整个关掉）。
- 双向联动要防成环：A 生成 B、B 又生成 A 会无限链式引爆。给生成的实体打来源标记（如 `_mod_from_rain_linkage`）并在反向生成时检查。
- 两个控制模板都靠 `main_script.update` 施放（火雨 `all/scripts.lua:8186`、雷暴 `kr1/game_scripts.lua:15823`），包装 `update` 比追 `main_script.insert` 可靠（`insert` 常被别的插件覆盖/截断）。


## 数据位置

| 内容 | 路径 |
|---|---|
| 四棵树的升级项定义 | `KingdomRushDove/kr1/upgrades.lua` |
| 中文名 / 描述 | `KingdomRushDove/_assets/kr1-desktop/strings/zh-Hans.lua` |

`upgrades.lua` 的树边界（顶层 `upgrades.list = {{ ... }, { ... }, ...}`）：

| list_id | 行区间（v2.0.3.3） |
|---|---|
| 1（科技一） | 121 ~ 385 |
| 2（科技二） | 386 ~ 678 |
| 3（科技三） | 679 ~ 955 |
| 4（科技四） | 956 ~ 1221 |

行号会随版本漂移，**以 `upgrades.list = {{` 与 `}, {` 分隔符为准**，别硬记行号。

## i18n 键规则

`all-desktop/screen_map.lua:4695`：

```
_("UPGRADE_" .. UPGR.list_id .. "_" .. upgrade_name .. "_NAME")
_("UPGRADE_" .. UPGR.list_id .. "_" .. upgrade_name .. "_DESCRIPTION")
```

所以 `UPGRADE_4_thunder_typhoon_NAME = "洗礼"` 表示 **list 4 的 `thunder_typhoon`**。
查某个 key 的中文名：

```bash
grep -n "UPGRADE_4_thunder" KingdomRushDove/_assets/kr1-desktop/strings/zh-Hans.lua
```

**不要**用 `grep "艾纳尼"` 直接定位 —— 中文名散在 changelog 里，会误导；按 `UPGRADE_<list_id>_<key>_NAME` 精确匹配。

## 排查套路："面板名字和游戏里不一致"

1. 在 `zh-Hans.lua` 里 grep 你看到的中文名 → 得到它的 `UPGRADE_<list_id>_<key>` 前缀，这就是**真实 key 和所属树**。
2. 到 `upgrades.lua` 对应 list 段确认该 key 存在，看 `class` / `level` / `price` / `icon`。
3. 回插件里 grep 这个 key；如果没有，说明插件根本没接管它（不是名字写错，是整项缺失）。
4. 若要接管，同时补三处：开关映射表、`patch_templates`（或等价的后处理点）里的数值覆盖、配置默认值与标签。

## 坑

- **给天赋加面板条目必须同时补两处**：配置默认值表里 `{name}_enabled = true`，以及 `key_label_map` 里 `{name}_enabled = "显示名"`。只补标签不补默认值 → 面板卡片**没有图标位、没有开关按钮**，只剩几行孤立数字（`build_talent_groups` 只按 `*_enabled` 键建组）。2026-10-21 踩过的真坑。
- 数值标签支持 `"中文名[副标题]"`，卡片里拆成主标题 + 小字副标，用来区分 `闪电数量[主闪电]` / `额外闪电数量[额外闪电]` 这类同组字段。
- **别按"第 N 级"跨树对齐**。科技三的第 6 级是 `thunder_level_6`，科技四的第 6 级是 `thunder_typhoon`，key 和效果都不一样。
- **跨树合并会让玩家"白拿"另一棵树独有的最高级**。插件若用 `get_upgrade` 遍历全部 list 合并，必须加"当前科技树确实拥有该项"的守卫，否则科技三玩家也会吃到洗礼的 10 发闪电。
- ⚠️ **但反向也成立：隔离做过头同样是 bug**。如果插件给火雨↔雷暴做了双向联动（施放任一方同时带出另一方），**联动开启时两个技能都会真实出场，此时两边的天赋都该生效，绝不能按树隔离** —— 否则科技一的玩家联动出的雷暴拿不到雷暴天赋，科技三的玩家联动出的火雨拿不到火雨天赋，等于一半配置永远无效。正确判据是「按联动状态决定是否隔离」：联动开 → 跨树合并；联动关 → 只认当前树。2026-10-21 实测数据（`levels.rain=0`、火雨 +9 发/+47 伤害、雷暴 count13、洗礼 17/19/减速.22/extra7）：
  - 联动开：四棵树全部 `fireball=3+9, dmg=30+47, thunder=17/19/extra7`
  - 联动关：树1/2 → `fireball 12 / dmg 77 / thunder 3/0`；树3 → `fireball 3 / dmg 30 / thunder 13`；树4 → `fireball 3 / dmg 30 / thunder 17/19/extra7`
  - 缓存键必须带上联动状态（如 `..":"..(linkage and "L" or "S")`），否则切换开关后拿到旧结果。
- ⭐⭐ **守卫必须下沉到 `get_upgrade` / `has_upgrade` 本身，放在"应用层"（拿返回值再判断要不要写模板）是无效的**。原因：hook 的 `get_upgrade` 被本体的 `patch_templates` 直接调用，本体拿到非 nil **就按自己的硬编码写模板**（`upgrades.lua:2440` 起：`thunder_level_1` → `thunders[1].count=6`、`thunder_typhoon` → count 10 / `extra_duration=4`）。所以在 `apply_post` 里加 `in_current_tree` 只能挡住插件自己写的那一份，挡不住本体那一份。正确做法：在 `get_upgrade` 的合并循环里对跨树独有的 key 加 `id == self.list_id`，语义与本体 `get_upgrade` 只查 `self.list[self.list_id]` 一致。2026-10-21 实测：只在 apply 层加守卫时，`list_id=1` 仍拿到 `count1=10 / extra_duration=4`；下沉后变成模板原值 `3 / nil`。
- 同理，**测试里"四棵树结果一致"这类断言会掩盖跨树泄漏**，改成跨树后需重写：断言"非属主树与关闭该项时逐模板完全相同"（`same_templates`），而不是断言"四棵树都等于配置值"。改了隔离规则后，要补成「联动开／关 × 四棵树」两轮矩阵，单态断言等于没测另一半。
- **测"本体可达性"这类与联动无关的组，先显式把联动关掉**（`cfg.rain_thunder_linkage_enabled=false`）。否则默认 `true` 会让"雷暴天赋在别的树不可见"这条断言失败，而失败原因跟被测目标无关。
- **`price` 在多树合并里是相加的**，`level` 取最小。合并出来的 price 不能直接当"这个科技要几颗星"用。
- 科技四的 `thunder_typhoon` icon = 21，和 `thunder_level_1`/`thunder_typhoon` 系列复用同一张，别拿 icon 判唯一性。
