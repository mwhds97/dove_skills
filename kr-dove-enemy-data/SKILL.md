---
name: kr-dove-enemy-data
description: 从《王国保卫战 Dove》游戏数据里按关卡号/模板名提取敌方单位数据（代码名、中文名、血量、攻击、护甲、速度、赏金、扣命、飞行/被动、技能与光环），用于设计出怪或做数值交叉对照。当需要"查某关有哪些敌人""某敌人的血量攻击多少""整理敌方单位数据表"时使用。
agent_created: true
---

# KR Dove 敌方单位数据提取

适用：需要某关的出怪清单、某敌人的数值、或整理一份敌方单位参考表（设计新关卡出怪、平衡数值、对照原版）。

## 数据位置（都在 KingdomRushDove/ 下）

| 内容 | 路径 |
|---|---|
| 出怪清单 | `kr1/data/waves/levelNN_waves_campaign.lua`（**关卡序号 = 文件名序号**，如第17关→level17） |
| 普通敌人模板 | `kr1/enemies.lua`（结构 `RT("名字","enemy")` 起，到下一个 `RT("` 结束） |
| BOSS 模板 | `kr1/boss.lua`（如 `eb_kingpin`） |
| 子弹/投射物 | `kr1/enemies.lua` 或 `kr1/game_templates.lua`，`RT("名","arrow"/"bolt_enemy")` |
| 中文名 | `_assets/kr1-desktop/strings/zh-Hans.lua` |
| 关卡分支配置 | `kr1/data/waveconfigs/levelNN_waves_campaign_config.lua`（通常为空） |

## 字段对应关系

| 含义 | 字段 |
|---|---|
| 血量 | `tt.health.hp_max`（可为数组=多命，对应 `tt.health.hp_max_evolved` 进化形态血） |
| 物理护甲 | `tt.health.armor`（0~1 减伤比例） |
| 魔法护甲 | `tt.health.magic_armor` |
| 近战伤害 | `tt.melee.attacks[1].damage_min/max`（`cooldown` 冷却） |
| 范围近战 | `tt.melee.attacks[1] = CC("area_attack")` + `damage_radius` |
| 远程伤害 | **不在 enemy 里**！看 `tt.ranged.attacks[1].bullet` 指向的**子弹模板**的 `tt.bullet.damage_min/max` |
| 速度 | `tt.motion.max_speed = x * FPS`，**FPS=30** → 像素/秒 = x×30 |
| 赏金 | `tt.enemy.gold` |
| 漏怪扣命 | `tt.enemy.lives_cost`（缺省 = 1） |
| 飞行 | `tt.vis.flags` 含 `F_FLYING` |
| 不攻击 | `tt.main_script.update = scripts.enemy_passive.update` → **只推进不攻击**（如石像鬼、巨型黄蜂、火箭飞兵） |
| 光环/技能 | `tt.auras.list[1].name` → 查 `RT("aura名","aura")` 的 `aura.radius` / `aura.mod`；`tt.timed_attacks` 定时技能 |
| 特殊死亡 | `tt.death_spawns.name`（如巨鸟骑士死亡掉落巨鸟） |

## 中文名键规则

`{模板名全大写}_NAME`，如 `ENEMY_BANDIT_NAME`、`ENEMY_SHAMAN_MAGIC_NAME`；BOSS 如 `EB_KINGPIN_NAME`。同键还有 `_DESCRIPTION` / `_SPECIAL` / `_EXTRA`。

## 难度系数（GS，`kr1/game_settings.lua`）

- 血量 `difficulty_enemy_hp_max_factor = {1.3,1.65,1.65,2}`（简单/普通/困难/噩梦）
- 速度 `{1.2,1.2,1.25,1.25}`；赏金 `{1,1,0.9,1}`
- 远程冷却 `{1,0.9,0.9,0.8}`；定时技能冷却 `{1,0.9,0.9,0.7}`；护甲加成 `{0,0,0.1,0.1}`
- **游戏内实际血量 = 模板 hp_max × 难度系数**（`hp_max_evolved` 不参与）

## 操作流程

1. 提取某关出怪清单（去重统计）：
   ```bash
   python -c "import re,collections;s=open('kr1/data/waves/level17_waves_campaign.lua',encoding='utf-8',errors='ignore').read();c=collections.Counter(re.findall(r'creep=\"([^\"]+)\"',s));[print(k,v) for k,v in sorted(c.items())]"
   ```
2. 按模板名提取属性：用 `scripts/extract_enemies.py`（改文件头的关卡路径/模板列表即可），它会跨 enemies.lua/boss.lua 定位 `RT(...)` 块、解析字段、匹配中文名，输出可读报告 + JSON。
3. 远程单位记得再查子弹模板拿伤害（脚本已含该步骤）。

## 动画键与贴图组验证（移植友军版前必查）

1. **动画键**：运行时动画库来自 `kr1/data/game_animations.luac`（`all/animation_db.lua:95` 加载），luac 里字符串未加密，直接正则提：
   ```bash
   python -c "import re;data=open('kr1/data/game_animations.luac','rb').read();[print(k.decode()) for k in sorted(set(re.findall(rb'enemy_bloodshell[a-zA-Z_0-9]*',data)))]"
   ```
   键名 = `{模板prefix}_{动画名}`，友军士兵模板需要 `walkingRightLeft/walkingUp/walkingDown`（walk angles）、`idle`、`attack`、`death`。水栖敌人另有 `enemy_xxx_water_*` 变体。
2. **贴图组归属**：全帧图集在 `_assets/kr1-desktop/images/fullhd/*.luac`（同名 .dds 是贴图）。图集帧名是**帧序列命名**（如 `BloodShell_0001`起137帧），**大小写/拼写与模板 prefix（enemy_bloodshell）不一致**——找归属要按敌名主体（bloodshell）全量扫 luac：
   ```bash
   python -c "import glob;[print(f) for f in glob.glob('_assets/kr1-desktop/images/fullhd/*.luac') if b'bloodshell' in open(f,'rb').read()]"
   ```
   得到组名（如 go_enemies_rising_tides）后，确认它在插件的 required_textures / director.load_texture_groups 列表里，否则跨关卡加载会黑贴图。

## 坑

- 波次 .lua 是压缩成单行的大文件，别用 Read 逐行看，用正则提 `creep="..."`。
- `enemy_passive` 单位不会攻击，设计出怪时别当输出/肉盾用。
- 光环单位（萨满系）会互相加 buff，成群时要按"优先点杀支援单位"来平衡。
- 同一模板可能在多处被二次赋值，脚本取**最后一次**赋值。
- 水栖敌人（valid_terrains 含 TERRAIN_WATER、main_script=enemy_mixed_water）改友军士兵时，nav_grid 不支持水面寻路——克隆后 `enemy=nil`（移除 valid_terrains）+ `water=nil`，按陆地单位处理。
