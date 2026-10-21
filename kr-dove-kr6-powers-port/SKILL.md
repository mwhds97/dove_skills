---
name: kr-dove-kr6-powers-port
description: 把《王国保卫战6 Genesis》的法术（rain_of_fire/reinforcements/aspect_of_sol/musketeers/thunder_zapper/royal_edict/teleportation_sigil/soaring_shop/wintersongs_wrath）移植进《王国保卫战 Dove 版》插件 `kr6_powers` 的成套做法。核心是**口径统一为"取满级数值、不搬 KR6 的 XP/升级成长系统"**，以及移植路上四个必踩的差异：①Dove 的 `armor/magic_armor/poison_armor` 是 **0~1 比例**（填 40 会被夹成 1.0 = 完全免疫）；②选敌链路不同（KR6 走 `GUI_MODE_SELECT_POINT → can_select_point_fn`，Dove 按钮**直接 cast 不走该链**）；③KR6 帧无 baked `ref_scale` ⇒ 搬素材一律先 ×0.7111；④KR6 与 Dove 同功能帧**前缀常常不同**，抄 KR6 帧名必崩。另含远程士兵（火枪手）路线、`balance` 每个键必须真落进模板的逐字段核对、以及 10 个离线探针的断言清单。§15 是**换源版本**（如 KR5 Alliance 叛军民兵 → 王国骑士）的增量经验：图集 `alias` 陷阱、动画段来源、死旋钮探测、7 触点接入清单。触发词：移植 KR6 法术、移植 KR5 法术、kr5 alliance、kr6_powers、Genesis 法术、王牌火枪手、罗索化身、火雨、援军、royal_edict、王国骑士、rebel_militia、thunder_zapper、法术 CD、KR6/KR5 数值表。
agent_created: true
---

# KR6(Genesis) 法术 → Dove 移植

**已落地 11 个**（kr6_powers v0.33）：火雨 rain_of_fire / 援军 reinforcements / 罗索化身 aspect_of_sol /
王牌火枪手 musketeers / 皇家号令 royal_edict / 王者驰援 denas_summon / **王国骑士 kingdom_knight（KR5，§15）** /
**暗影弓手 shadow_archer（KR5）** / **精灵援军 elven_reinforcements（KR3，§17）** /
**前线援军 frontiers_reinforcements（KR2，§17.2）** /
**龙息法杖 dragonfire_staff（KR3 手机版道具，§17.2 ⑫~⑮）**。
待做：KR6 的 `teleportation_sigil` · `soaring_shop` · `thunder_zapper` · `wintersongs_wrath`。

> 数值表**不写这里**（会过期）：→ 项目根 `KR6法术系统数值总表.md` + 插件 `kr6_powers/README.md`。
> 特效资源审计 → 项目根 `KR6法术特效资源审计.md`。
> 代码权威值 = `mods/local/kr6_powers/kr6_powers_balance.lua` **顶部字面量**（KR6 原值写在注释里留对照）。

## 0. 口径（用户 2026-10-15 定）

- **取满级（lvl_3 那套）数值做进插件，不移植 KR6 的 XP / 升级成长**。
  范式：**不要**参考 AppData 的 `royal_edict_skill` 插件（用户 2026-10-17 明确"那个插件不适合
  作为参考，他甚至无法正常运行"；且其注释错 4 处：CD 40↔50、基础倍率 1.8↔1.75、
  l2a 方向反、l6 语义反）。**正确范式 = 本体**：塔增益 `scripts.mod_high_elven`
  （kr1/game_scripts.lua:62）+ 到期移除 `scripts.mod_ban`（all/scripts.lua:8522）
  + 掉金 `extra_loot`（kr1/game_scripts.lua:1156/1182）。
- **CD 由用户定**（例：火枪手 KR6 满级 18s，用户拍板 15s）。**移植技能数值改不改由用户定，我不擅改**。
- KR6 素材动画只收录满级那套前缀（例：火枪手只收 `Mosq3`，`Mosq1/Mosq2` 是 l3 之前形象，不要）。

## 1. 插件文件分工（`mods/local/kr6_powers/`）

| 文件 | 职责 |
|---|---|
| `kr6_powers.lua` | 入口：`ATLAS_NAMES`、`register_localization`（法术名 + 士兵随机名）、`SOUND_DEFS`、`E:load` 后 `pcall(Spells.install_*_mechanics)` |
| `kr6_powers_spells.lua` | 大头：`*_ANIMS` 动画注册表、`register_animations()`、`register_templates()`、`SpellTable.<法术>` 施法注册、自定义 hook / 脚本 |
| `kr6_powers_balance.lua` | 权威数值（顶部字面量）+ `apply(cfg)` 把面板键覆盖进 `B.*` |
| `kr6_powers_config.lua` | 面板项生成物（**别手写**，用生成器；见 `kr-dove-plugin-config`） |
| `kr6_powers_room.lua` | 局外选择面板（UI 细节见 `kr-dove-ui-panel`） |
| `kr6_powers_buttons.lua` | 局内按钮 + 热键（热键有总开关 `HOTKEYS_ENABLED`） |
| `kr6_powers_store.lua` | 存档层（选中了哪些法术 / 等级） |

## 2. ⚠⚠ 移植路上的四个硬差异

### 2.1 armor / magic_armor / poison_armor 是 **0~1 比例**，不是百分数
`U.calc_protection` 收尾是 `km.clamp(0, 1, ...)`（`all/utils.lua:2008`）。
**填 40 会被夹成 1.0 = 完全免疫**。KR6 写 40 的地方这里必须写 **0.4**。
⚠ 但**界面显示的是 ×100 后的整数**（护甲 0.4 显示成「40」）⇒ 用户按界面读数说话时，
  要按「界面标度」理解并换算（详见本节后面的「数值单位」小节）。
（其余 KR6 百分比字段也逐个人工换算，别整块抄。）

### 2.2 选敌链路不同
KR6 靠 `GUI_MODE_SELECT_POINT → can_select_point_fn` 让玩家点地选目标；
**Dove 的插件按钮是"点下去直接 cast"，不走这条链** ⇒
选敌必须由自己的 `M.cast` 在**入队前**完成（`pick_target_on_cast` 之类），
否则法术放出去 `target` 是 nil，要么不生效要么崩。

### 2.3 KR6 帧无 baked ref_scale ⇒ 搬素材先 ×0.7111
Dove 世界尺寸 = 帧 size × 帧 baked `ref_scale`（`image_db.lua:505`，本体 = 0.5）
× 图集 load scale（fullhd = 0.7111）× 模板 `sprite.scale`。
**KR6 帧的 baked = 1** ⇒ 直搬会大 1/0.7111 ≈ 1.4 倍。插件做法：图集以 `ref_scale = 1` 加载，
配合模板 `scale` 反算（例：援军 KR6 字面 0.9 → 终版 0.64，用户拍板）。
⚠ `hit_offset` / `health_bar.offset` / `unit.mod_offset` / `melee_slot_offset` 是**世界像素偏移，
不随 `sprite.scale` 缩放** ⇒ 改 scale 必须同步乘同倍率，否则血条浮空。
详见 `kr-dove-ui-panel`。

### 2.4 KR6 与 Dove 的"同功能帧"常常**前缀不同** —— 抄 KR6 名必崩
实测：点士兵崩 `kui.lua:529 attempt to index local 'ss'` + `image_db.error Sprite X was not found`。

| 功能 | KR6 名 | Dove 名 |
|---|---|---|
| 单位信息条头像 | `gui_bottom_info_image_soldiers_0068` | `kr6_info_portraits_soldiers_0068`（编号一一对应，像素比对实证） |
| 即死"爆头"标记 | `pop_headshot` | `pop_instakill`（`all/templates.lua:710`） |

**权威查证工具** = `.workbuddy/_krab_check.py`（按 `lib/klove/atlas_binary.lua` 的 KRAB 格式逐字节解析
Dove 全部 `.bin`；473 bin ⇒ 277730 帧名，0.8s，缓存 `_krab_index.json`）。
常驻体检 = `.workbuddy/check_kr6_frames.py`。
⚠ **离线 `love_stub` 不加载 KRAB ⇒ 静态 grep 查帧名全是假阴性**，别用 grep 代替这两个工具。
动画键层面的检查见 `kr-dove-offline-lua-harness` 的「动画键 / 帧名离线校验」一节。

## 3. ⭐⭐⭐ 派生模板必须逐字段核对：`balance` 里有 ≠ 模板读了

**两次血案，同一类错**：

1. 火雨漏写 `tt.bullet.damage_radius` ⇒ 面板上调"爆炸半径"对流星 AOE **静默无效**
   （模板继承了本体默认 60，面板改的那个键没人读）。
2. 火枪手「子弹削甲」：模板写死 `tt.bullet.reduce_armor = 0`，旁边留了一句
   **"l4b 会在 insert 时改成 `MK.l4b.reduce_armor`"** —— 而**那句所说的代码从未存在**
   （`grep kr6_mk.reduce_armor` 零命中）。削甲值只被塞进士兵状态表 `tt.kr6_mk.reduce_armor`，
   **全项目无人读取**。⇒ 面板能改、balance 有值、探针全绿，**游戏里每发子弹都不削甲**。

### ⭐⭐ 判据：探针要断言**最终消费点**，不能只断言 `balance` 或"中间状态表"

这类死旋钮的共同形态：**值被写出去了，但没有任何路径把它送到引擎真正读的地方**。
各法术的"最终消费点"不一样，要顺着引擎调用链找：

| 机制类型 | 最终消费点（要断言的地方） | 引擎读它的地方 |
|---|---|---|
| 子弹类（削甲 / 伤害 / 伤害类型 / xp） | **子弹模板** `tt.bullet.<字段>` | `SU.create_bullet_damage`（`all/script_utils.lua:591`）→ `d.reduce_armor = bullet.reduce_armor` → `U.calc_protection` |
| 光环 / 持续伤害 | **aura 模板** `tt.aura.<字段>` | aura 脚本按 cycle 结算 |
| 士兵属性 | **士兵模板** `tt.health/motion/melee/...` | 模板即运行时数据（quickcopy 深拷贝） |
| 面板可改的意图 | **`<entry>_config.lua` 值表** | `balance.apply` |

规则：
1. `balance.lua` 里每个键，都要在 `register_templates()` 里找到**读取点**；找不到 ⇒ 就是死旋钮。
2. ⚠ **不要相信注释里"运行时会改写"的说法** —— 去 grep 那句话描述的函数/字段是否真的存在。
   本次就是被一句假注释骗过（而且假注释的存在让代码"看起来很完整"）。
3. 每个法术的探针都要**断言最终消费点**，且每条断言配一句"改回旧值会 FAIL"的注释；
   **必须做负向自测**（改回错值跑一遍确认 FAIL，再还原 + 比对 md5），否则无法区分门禁真假。
4. 面板项生成后，跑 `verify_kr6_config_panel` 确认"改了面板值 → 模板值跟着变"。
5. 发现"中间状态表里有、但没人读"的字段，**直接删掉**（避免第二个死旋钮），
   并在探针里断言它**不再存在**（`k.reduce_armor == nil`）。

### ⭐⭐⭐ 改数值一定要**重生成 config** —— 运行时权威是 config，不是 balance

`kr6_powers_balance.lua` **文件末尾**有一句 `apply(read_config())` ⇒
**require 的瞬间就会用 `<entry>_config.lua` 覆盖 balance 顶部字面量**。

| | 角色 |
|---|---|
| `kr6_powers_balance.lua` 顶部字面量 | **文档 / 生成源**权威（`_gen_kr6_config.py` 从它产出面板默认值） |
| `kr6_powers_config.lua` | **运行时权威**（玩家面板值与默认值都读它） |

⇒ **改 balance 字面量但不跑生成器 = 运行时仍是旧值**（2026-10-16 负向自测踩到：
把 balance 的倍率改回 12 跑探针，**仍然全绿** —— 因为 config 里还是 4）。

**正确流程**（六处联动）：
```bash
# 1 改 balance 顶部字面量
python .workbuddy/_gen_kr6_config.py     # 从 balance 反查键 + 运行时默认值
python .workbuddy/_emit_kr6_config.py    # 生成面板三件套（值表/键序/标签）
python .workbuddy/check_kr6_config.py    # 自检：config 默认值 == balance 运行时值
```

⭐ **做负向自测时要改 `config`，不是只改 `balance`** —— 否则测的是"一个不生效的位置"，
会得到"门禁失效"的**假结论**（我就被这个骗了一次）。

### ⭐⭐⭐ 数值单位：**界面标度 vs 引擎比例**（最容易被用户和自己双向误读）

判断用户说的数字是哪个标度，**看他在界面上看到什么**：

| 概念 | 界面显示 | 引擎内部 | 换算 | 出处 |
|---|---|---|---|---|
| 单位护甲 | `40`（整数） | `0.4` | **×100** | `GU.armor_value_desc_detailed` = `string.format("%d", v*100)`（`all/gui_utils.lua:100-107`） |
| 大部分百分比字段 | `40%` | `0.4` | ×100 | 同上类 |
| 冷却 / 时长 | 秒 | 秒 | 1:1 | — |
| 帧间隔 | — | 秒 | `fts(n) = n/30` | `store.tick_ts` 以秒计 |

**血案**：用户说「削甲 1.5」→ 我按引擎比例实现成 `0.4 − 1.5`（一次归零）；
用户看到界面上护甲纹丝不动（因为他要的是**真的把护甲数字降下来**），反馈"并没有减少"。
⇒ **正确做法：balance 里存界面标度（1.5），代码里统一 `* 0.01` 换算**，并在
`balance` 注释 + 面板标签（`火枪 每击降甲(界面0~100标度)`）+ 探针里三处钉死这个换算。
面板标签**必须标出标度**，否则下次自己也会读错。

### ⭐⭐⭐ 「降低敌人护甲」只有 `SU.armor_dec` 才是真的（`bullet.reduce_armor` 不是）

- `bullet.reduce_armor` 只参与**这一发**的减免计算
  （`U.calc_protection`：`protection = health.armor - d.reduce_armor`），
  **完全不改 `health.armor`** ⇒ 玩家在信息面板上看不到任何变化。
- 要让护甲**真的降下来**（持久、可累加、别的塔也受益）用引擎自带：
  ```lua
  SU.armor_dec(target, value)   -- all/script_utils.lua:317
  -- → armor_buff -= value * (1 - armor_resilience)
  -- → armor = clamp(0, raw_armor + armor_buff)
  ```
  值同样要 `*0.01`（见上表）。
- ⚠ `armor_resilience`：本体 **`boss.health.armor_resilience = 0.5`**（`all/templates.lua:991`）
  ⇒ **Boss 吃到的降甲效果减半**（自带机制，不是 bug）；普通敌人默认 0（`components.lua:47`）。
- ⚠ 护甲被 clamp 到 0、不会变负；降甲**不随时间恢复**（要到期恢复就得做 modifier）。

### ⚠⚠ 负向自测可能抓出**假门禁**：只测"函数行为" ≠ 测"调用点在"

本轮真实教训：给每个断言都做了负向自测，其中一条却**删掉调用后仍然全绿** ——
因为那组断言是**直接调用被导出的函数**测行为，而没断言 **HOOK 里是否真的调它**。
⇒ 补了 `mk_code:find('M%.mk_armor_dec_apply%s*%(%s*target%s*%)')` 才抓住。
**规矩：新增一个运行时机制，必须同时有**
① `balance`/模板值断言 ② **函数本身的行为断言**（喂假数据跑真引擎函数）
③ **调用点断言**（源码里真的有那句调用）④ **顺序断言**（在它该在的位置之前/之后）。
⛔ 只做②＝"函数是对的但没人用"（就是死旋钮的另一种形态）。

### ⚠ nil 兜底：往模板写值也要防 nil

`tt.bullet.reduce_armor = MK.l4b.reduce_armor or 0` —— 若该键为 nil，会经
`d.reduce_armor = bullet.reduce_armor` 传到 `health.armor - d.reduce_armor` 做算术 ⇒
抛 `attempt to perform arithmetic on a nil value`（同 `damage_type = nil` 覆盖模板默认值
那类坑，见 MEMORY）。**凡引擎会直接参与算术的字段，一律 `or <安全默认>`**。

## 4. ⭐⭐⭐ 远程士兵路线（火枪手 musketeers，2026-10-16 通透）

目标：一个**会开枪**的召唤士兵 + 4 个特殊机制，且**零侵入**引擎。

- 基类 `re_farmer` + **`E:add_comps(tt, "ranged")`**；
- **复用本体** `scripts.soldier_reinforcement.update` —— 它**原生支持远程**
  （`if this.ranged then SU.y_soldier_ranged_attacks(...)`），本体 `re_legionnaire_ranged` 用的就是这条；
- 子弹全走本体射线弹 `scripts.ray5_simple.update`（**原生消费** `bullet.hit_payload`，见 `kr1/game_scripts.lua:17459`，
  命中自动创建 aura）+ `bullet.hit_fx` ⇒ **l6 爆裂弹无需自写脚本**；
- 4 个特殊机制 = 一个 **HOOK `SU.y_soldier_do_ranged_attack`**（`all/script_utils.lua:1597`），
  在**开火前**按条件切 `this.ranged.attacks[1].bullet`：
  ```lua
  HOOK(SU, "y_soldier_do_ranged_attack", function(next, store, this, target, attack, pred_pos)
      local mk, ra = this.kr6_mk, this.ranged and this.ranged.attacks[1]
      if mk and ra and target then
          if not mk.l6_shot then            picked, ra.animation = mk.bullet_l6, "special_attack"
          elseif M.mk_is_disabled(store, target) then  picked, ra.animation = mk.bullet_l4a, "ranged_attack"
          elseif <血量≤阈值 and 非免即死名单 and math.random() <= chance> then
                                             picked, ra.animation = mk.bullet_l5b, "ranged_attack"
          else                               picked, ra.animation = mk.bullet_basic, "ranged_attack" end
          ra.bullet = picked
      end
      local done = next(store, this, target, attack, pred_pos)
      if done and mk and ra and not mk.l6_shot then mk.l6_shot = true; ra.animation = "ranged_attack" end
      return done
  end)
  ```
  ⚠⚠ **必须 HOOK 这一层**：上一级 `y_soldier_ranged_attacks` 还没选出 target，
  而这里要读 `target` 判"残废/血量"。⚠ 这个 HOOK **每次开火调一次**（不是每帧）⇒ 不会堆积实体。
- 子弹必备字段：**`tt.bullet.hit_time` 必须显式写**（Dove 的 bullet 组件默认值表**不含**它，
  `all/components.lua:945-985`；`ray5_simple.update` 会无条件 `if b.hit_time > fts(1)`，
  `kr1/game_scripts.lua:17407` ⇒ nil 时**每帧刷屏报 `attempt to compare number with nil` 且子弹不结算**）。
  同理补 `draw_order`、`image_width`、`ray_duration`。⚠ 这类"**字段缺失**型 bug 必须逐字段显式断言"，
  只查"已有值对不对"发现不了。
- **双动画通道**：`angles.ranged_attack = {"shoot","shootup","shootdown"}`、
  `angles.special_attack = {"special","specialup","specialdown"}`（KR6 同款角度分档），
  攻击脚本读 `attack.animation` 的**组名**，由 `U.animation_name_for_angle` 展开。

## 5. ⭐⭐⭐ 派生士兵必须显式覆盖 `main_script.insert`

`re_farmer` 的 insert 是 **`fn_group`**，内部会执行
`prefix = this.template_name .. "_" .. i`（i 随机 1~3）⇒ **覆盖模板上的 `render.sprites[1].prefix`**
⇒ 实测报 `kr6_powers_mk_soldier_1_idle not found`。

修法：`tt.main_script.insert = scripts.soldier_reinforcement.insert`（纯净版）。
⚠ **探针只查"模板上的 prefix 值"发现不了**（覆盖发生在运行时 insert 里）⇒ 必须断言
`main_script.insert == require('scripts').soldier_reinforcement.insert` 本身。
⚠ 反向的合法用法：援军**故意**让 insert 补变体号 —— 模板静态 prefix 写 `"kr6_re_lvl3_"`（带尾下划线），
insert 内 `e.render.sprites[1].prefix = "kr6_re_lvl3_" .. i`。

## 6. ⭐⭐ 派生士兵前先看基类给了什么（别照抄 KR6）

- `re_farmer` 继承的本体 `scripts.soldier_barrack.get_info`（`all/scripts.lua:522`）
  **原生同时算近战 + 远程**（返回 `damage_min/max` + `ranged_damage_min/max` + 两者 cooldown + `no_ranged` 标记）
  ⇒ **不要覆盖 `info.fn`**，自写会丢字段（信息条显示不全）。
- **士兵随机名字要自己注册**：`tt.info.random_name_format` + `random_name_count`
  ⇒ insert 拼 `i18n_key` ⇒ 信息条取 `_(i18n_key .. "_NAME")`（`game_gui.lua:3044`）。
  **Dove 本体没有 KR6 的 `SOLDIER_<X>_*` 键**，要自己在入口 `register_localization` 里写。
- `re_farmer` 的 `insert` 是 `fn_group`（见上条）；援军走 `scripts.soldier_reinforcement.*`。

## 7. ⭐ 三个"独立字段、无联动"的时长

| 字段 | 含义 |
|---|---|
| `tt.reinforcement.duration` | 士兵存活时长 |
| `tt.aura.duration` | 光环实体存活时长 |
| `tt.modifier.duration` | 单条 mod 持续时长 |

改一个必须手动跟上另外两个。探针要断言三者一致。
（`aura.requires_alive_source = true` ⇒ 兵死 buff 自动失效，不会"兵没了 buff 还在"。）
⚠ 特殊兵模板名是 **`kr6_powers_re_special`**（不是 `_special_soldier`）。

## 7-ter. ⭐⭐⭐ 搬 KR6 的 exo 骨骼动画（2026-10-17 皇家号令首次，五个硬事实）

> 触发：用户说"原版特效有个**人**/样子不对，实在不行 exo3 吧" —— 静态帧 + tween
> 替代方案在**"有角色登场"**这类特效上不成立（皇家号令的国王仪仗队），必须搬骨骼。

1. **KR6 的 `.exo3` 是文本 Lua**（头 `return {version=3,...}`）—— Dove 的
   `EXO:load_packed` 只吃二进制（magic `EXO3`）⇒ **存成 `.lua`** 走 `load_lua`
   （`exoskeleton.lua:542`）。拷成 `.exo3` 会静默读不到。
2. **动画键 = `<exo_name>_<anim_name>`**（`exoskeleton.lua:124-133` 注册）
   ⇒ 模板里 `render.sprites[1].prefix` 填 **exo_name**（不是帧前缀！），
   `name` 填动画名 ⇒ 与 `render.lua:398` 的 `prefix.."_"..name` 拼出同一个键。
3. **parts 帧名前缀只改行首**：`sed "s/{'royal_edict_/{'kr6_royal_/g"`。
   ⚠ 全局 sed 会连**中段**一起改（`towerbuff_asst_royal_edict_buffspike`）⇒ 与图集
   （`rn()` 只换开头）不一致 ⇒ 缺件。图集脚本也要**搬 alias**（源图集常把
   `trumpets_asst_lena_confetti` 这类挂在别的 key 的 alias 下，而 exo parts 直接引用它）。
4. **`partScaleCompensation = 1.40625` = 1/0.7111** ⇒ KR6 已按 fullhd **预除** parts scale；
   插件图集同样 `ref_scale = 1` 加载 ⇒ **尺寸直搬就对，别再乘 0.7111**。
5. **加载**：HOOK `director.load_texture_groups`（`item_name == "game"`）里
   `EXO:queue_load(list)` + `EXO.exos_count[name] = 999999` 防卸载（denas 范式）；
   `list` 用 `{name=..., path="plugins/<插件>/_assets/exo"}` 表形式。
   ⚠ **只 queue 不能 load** —— `EXO:load()` 由 director 进对局时统一跑；
   提前 load 会因 `A.db` 未就绪缺帧。

### 两个"静态检查查不出、只有实机/自查才发现"的坑

- 🔴 **`decal_scripted` 没有 tween 组件** ⇒ 给它设
  `main_script.remove = scripts.tween_utils.reverse_remove` 会在**实体移除时崩**：
  `game_scripts.lua:47622 attempt to index field 'tween' (a nil value)`。
  （`decal_tween` 自带 tween，是安全的那个。KR6 原版 decal 普遍不设 remove 钩子。）
  ⇒ 探针必须做**全库扫描**：`E.entities` 里凡 `main_script.remove == reverse_remove`
  的模板都要有 `.tween`（只断言模板字段 = 假门禁，跑不到移除路径）。
- 🔴 **exo 动画要"播"才会动**：模板写 `prefix/name/exo=true` 只保证渲染第 1 帧。
  必须在 `update` 里跑 KR6 那段：
  ```lua
  for i, v in ipairs(this.animations or {}) do
      if v[2] then   -- loop 条目
          if i == #this.animations then U.animation_start(this, v[1], nil, store.tick_ts, true)
          else U.animation_start(this, v[1], nil, store.tick_ts, v[3] or 1) end
      else U.y_animation_play(this, v[1], nil, store.tick_ts) end   -- y 前缀=协程等待版
  end
  m.ts = store.tick_ts     -- ⚠ 计时起点在动画播完后重设（否则 start 时长从 buff 时长扣掉）
  ```
  连带：模板 `tween.disabled = true` 时，**淡出前必须 `disabled = false`**
  （只设 `reverse` 不生效 ⇒ "啪"地消失）。

### 体检脚本要同步（否则假阳性）
- `check_kr6_frames.py`：图集生成器必须搬 alias（本项目的 `_gen_kr6_*_atlas.py` 已含）。
- `check_kr6_anim_keys.lua`：要**解析 exo 文本源**（`{name='X'}` → `<exo>_X`）纳入键集，
  否则用 exo 的模板全被误报"动画键未注册"（离线桩不跑 `EXO:load`）。
- ⚠ 探针里写源码断言时，**Lua pattern 里 `%{`/`%}` 非法** ⇒ 含花括号的片段用
  `find(s, 1, true)`（plain 模式），且 plain 模式下**不能再写 `%.`/`%(`**（会被当字面 `%`）。
- ⭐ **静帧"空帧"抽查**（索引有键 ≠ 图集有像素）：按 `f_quad` 裁切图集查 alpha 极值，
  全透明 = 隐形的另一类坑（帧名体检查不出）。PIL 一行：
  `img.crop((x,y,x+w,y+h)).getextrema()[3][1] == 0` ⇒ 空帧。
  新生成图集后建议跑一遍（本次 39 帧 0 空帧）。

## 7-bis. ⭐⭐ README 是**面向玩家**的，且与自检脚本强耦合

**定位**：`mods/local/kr6_powers/README.md` 面向**玩家**，风格对齐 `KingdomRushDove/mods/local/` 下
其它插件（`ember_hero` / `hero_zezitra` / `boss_crocs_hero` / `mercenary_tavern`）：
`一句话简介 → 功能介绍(主要特性/使用方法/游戏内配置) → 内容详情表 → 生效时机 → 已知边界 → 版本历史`。
👉 用户 2026-10-16 明确：**避免技术介绍**、**不要版权与致谢段**（本插件非外站 mod 移植）。
⇒ 引擎规则、面板三件套、开发工具命令、双侧同步、文件树、图集帧对应表、`slice_rect`、换算线等
**一律不进 README**（它们只留在本技能包 + 代码注释里）。

**⚠⚠ 但 README 被 `check_kr6_config.py` 第 7 项盯着**：那里用**表格格式正则**抽 README 的
关键定版值对照 `balance`，防文档漂移。**改 README 前先跑下面这段拿当前清单**
（别照抄旧清单 —— 条数随法术增长，2026-10-17 已从 12 条涨到 **20 条**）：

```bash
python - <<'EOF'
import io,re
s=io.open('.workbuddy/check_kr6_config.py',encoding='utf-8').read()
m=re.search(r'SPOT = \[(.*?)\n    \]', s, re.S)
for a,b in re.findall(r"\('([^']+)',\s*r?'([^']*)'", m.group(1)):
    print(a, '|', b)
EOF
```
把这些片段**逐字保住**，否则静默改坏门禁。改完跑
`python .workbuddy/check_kr6_config.py`（8 项，第 7 项逐条打 ✓）+ 推 AppData。

### 版本号：权威在 `config.lua`，README 是副本（易不同步）
- **`config.lua` 的 `version`**（插件管理器读它）是唯一权威；README 顶部
  `> 版本：**0.x**` 是文档副本 ⇒ 实测出现过 README 落后一版（0.13 vs 0.14）。
- README `## 版本历史` 用 **`### 0.x（日期）` 编号块**（用户实际写法，0.11~0.15 都是），
  **顶部版本号要与最新块一致**。
- ⚠ **升级版本号由用户决定**（用户 2026-10-17 明确要求过一次）⇒ 不要擅自升；
  一旦升，**两处一起改**（config.lua + README 顶部）+ 在版本历史加块。
- ⚠ 升 `version` 会触发 `__default_config` 合并（**仅覆盖用户改过的值**）⇒ 安全，
  用户面板里调过的项不会丢。
- `check_kr6_config.py` **只报事实不判断**（`当前 version = ...`，注释写明"版本号由用户定"）
  ⇒ 升版后它不报警，得人工核对两侧一致。
- ⚠ 版本历史**容易写错时序**：新条目忘了加、或把新功能塞进旧版本块
  （2026-10-17 就把皇家号令误写进 0.13、可调项数 117 也串了版）。改完回头核一遍
  「顶部版本号 = 最新块编号 ≠ 旧块数字」；`117`/`108` 这类**计数数字**也要与所属版本对齐
  （117 是皇家号令带来的，108 是火枪手带来的）。

## 8. 收尾自检（改完必跑）

```bash
# 语法（每次改了 lua 都跑；脚本只接单文件，批量用 shell for 循环）
python .workbuddy/lua_syntax_check.py mods/local/kr6_powers/*.lua    # ⚠ 实际要逐个传
# 帧名体检（KR6 专有帧名 + 帧是否存在于图集）
python .workbuddy/check_kr6_frames.py
# 动画键一致性（新增：动画键没注册会渲染成隐形，不崩）
python .workbuddy/check_kr6_anim_keys.py
# 全量探针（10 个 kr6 探针，~468 断言）
python .workbuddy/run_lua.py <项目>/KingdomRushDove .workbuddy/verify_kr6_mk.lua
# 双侧同步（dev ⇄ AppData）
python .workbuddy/compare_plugin_sync.py kr6_powers \
  --dev mods/local/kr6_powers --app "<AppData>/LOVE/kingdom_rush_dove/plugins/kr6_powers"
```

- 探针清单：`verify_kr6_rain` / `verify_kr6_re` / `verify_kr6_sol` / `verify_kr6_mk` /
  `sounds` / `config_panel` / `btn_layout` / `store` / `room_static` / `hook_return`。
- ⚠ **根目录插件（dev 在项目根 `mods/local/`）必须显式传 `--dev` / `--app`**，否则脚本按
  `KingdomRushDove/mods/local` 找，报"dev 目录不存在"。
- ⚠ AppData 侧 `config.lua` 的 `version` **在游戏运行时推留不住**（管理器会用内存旧记录重写）；
  **版本号由用户定，我不擅自升**，元数据 `config.lua` 一律游戏关闭后推。
- ⚠ 探针断言"期望值"会随用户调平衡而过期 ⇒ 报 FAIL 先查代码实际值 + 问用户，别直接改代码。

## 9. 用户协作约定（本项目特有）

- 移植数值改不改、改多少，**先给"原始值 + 偏离量"让用户拍板**；已拍板的定版（如局内按钮 0.42 /
  援军 scale 0.64 / 火雨 CD 45 / 号令 CD 46·持续 10）**别再动**。
- 用户会自己进游戏实测，**实测结果即最终验收**；离线全绿只是"机制跑得通"，不等于他觉得没问题。
- 报崩溃时通常直接贴日志（含 `文件:行号`）⇒ 按"崩溃位置 ≠ 崩溃原因"排查，先找真正的 nil 来源。

## 10. ⭐⭐⭐ 本体更新：**官方自带了法术系统**（2026-10-17 用户实测发现）

> 用户："游戏本体更新了，现在游戏本体也有了" —— 指底部按钮条多了官方「法术」入口。

### 本体现在是什么样
- **`KingdomRushDove/kr1/spell_system.lua`** = 本体法术系统，**注册表架构**（不是声明式 patch）：
  · `SPELLS.module_names = {"kr1.spells.royal_edict", "kr1.spells.aspect_of_sol",
    "kr1.spells.musketeers", "kr1.spells.wintersongs_wrath"}`（:25）
  · `SPELLS:get(id)` 懒加载（id = 路径末段）、`SPELLS.registry` 缓存、`SPELLS.max_level = 6`
  · 集成点（:4-8 注释）：`all/director.lua`（`SPELLS:set_selected` + 按选择 queue 资源）/
    `all/systems/level.lua`（热注册 + 预编译 + apply）/ `all-desktop/game_gui.lua`（Power3Button）
  · 存档字段 = **`user_data.spell_power_id`**（`kr1/data/slot_template.lua:20`）
- **本体已实现 4 个 KR6 法术**（`kr1/spells/*.lua`）：罗索化身 / 王牌火枪手 / 皇家号令 / 冬歌之怒
  ⇒ 与本插件**重复 3 个**（我们独有：火雨 / 援军）。
- ⭐ **`module_names` 是公开字段** ⇒ 理论上插件可 `table.insert(SPELLS.module_names,
  "kr6_powers.spells.xxx")` 把法术接进本体系统（共用官方面板/存档/按钮）。
  **这是架构级决策，未执行，等用户拍板。** 若要接，模块需满足 `spell.id` +
  `register_templates(E)` + `apply(level)`（`:40-56` 的校验）。

### ⭐⭐⭐ 本体已实现同款法术 ⇒ **mod 行为先照抄本体，别手搓**（2026-10-20 皇家号令崩溃）

用户原话："可以参考本体的写法，复制一份改过来，数值按照我们自己的。"

- 本体 `kr1/spells/royal_edict.lua` 的 `mod_power_royal_edict_towerbuff.main_script.insert`
  （:214-261）就是"挂到塔上的增益"的完整实现，手搓不如它。
- 踩的坑：我们写 `e.health.hp <= 0` 判"死兵"，本体写 `if e.health and e.health.dead`
  ⇒ 本体那种写法压根不碰 hp，天然免疫下面的 nil 时序问题。
- ⚠⚠⚠ **`health.hp` 初值是 nil**（`all/components.lua:27`），要等实体进 `simulation`
  才由 `health:on_insert_unconditional` 填成 `hp_max`（`all/systems/health.lua:583`）。
  而军营造兵是 `create_entity` → `queue_insert_entity` → **立刻**写 `b.soldiers[i]`
  （`all/scripts.lua:2045-2067`）⇒ 队列里那个兵 hp 还是 nil，
  `attempt to compare nil with number` 会把**整个插件**打成"已自动禁用"。
  ⇒ 铁律：**跨实体读 `health.hp` 前，先判 `health.dead` 或 `type(hp)=="number"`。**
- 另一个本体细节：重置 CD 是 `a.ts = store.tick_ts - a.cooldown`（判 `a.cooldown` 存在），
  不是 `a.ts = -1e99`（负无穷会污染任何拿 `ts` 做差值的逻辑）；
  而且本体**连兵营士兵**的近战/远程 CD 一起重置，手搓版漏了这一段。
- 探针要跟着改：断言从"ts 被推到极早"改成"`ts` 精确等于 `tick_ts - cooldown`，
  无 `cooldown` 字段的不碰"，并**注入原 bug 验有效性**（注入后 6 项 FAIL 才算测到）。

### ⭐⭐⭐ KR3（Origins）**内购道具**移植：素材与机制都在手机版数据里（2026-10-21 迈达斯之手）

Steam 版把内购道具的资源与 UI 逻辑**剥掉了**（模板残留、帧不全）⇒ 一律去手机版数据：

| 要找什么 | 去哪（均在 `<工作区>/base/assets/gc64/`） |
|---|---|
| 道具模板 / 计时脚本 | `kr3/game_templates.lua` / `kr3/game_scripts.lua`（**字节码**，要反编译） |
| 道具**真正生效**的逻辑 | `all-phone/game_gui.lua`（✅ **明文**，先 grep 这里，能省一次反编译） |
| HUD 元素定义 | `kr3-phone/data/kui_templates/game_gui.lua`（✅ 明文，`id=` / `image_name=` / `pos` / `dest` 全在） |
| 内购售价/倍率 | `kr3-phone/data/iap_data.lua` |
| 帧 | `base/assets/kr3-phone/images/iphonehd/<图集>.lua`（明文，含 f_quad/trim/size） |

- ⚠ **金币/经济类机制常挂在 UI 层，不在 systems**：迈达斯的加钱是
  `all-phone/game_gui.lua` 里 `["got-enemy-gold"]` 监听（`bonus = km.round(amount*factor)`
  额外入账），`kr3/game_scripts.lua` 的道具脚本**只负责设 `store.xxx_factor` 和计时**。
  ⇒ 光反编译 `kr3/` 会以为"这个字段没人读"，其实读点在 `all-phone/`。
- ⚠ **Dove 没有 `got-enemy-gold` 信号**：金币是 `all/systems/enemy.lua:102/:146`
  **内联**加的。⇒ 跨版本移植这类"掉金加成"只能 `HOOK(enemy, "on_update")`，
  用前后 `player_gold` 差值当本次掉金；**差值 ≤ 0 一律跳过**（买塔会让净增为负），绝不倒扣。
- 局内常驻 HUD 的挂法：`HOOK(GG, "init", …)` 后 `GG.window:ci("layer_gui_hud")` 拿层，
  `layer:add_child(view)`；每帧刷新挂 `HudCountersView:update`（关卡里必跑、开销最小）。
  ⚠ **不要**把交互元素挂进 `HudCountersView` 内部（它 `_disabled=true`）；纯显示虽可用，
  统一走 layer 更省心。坐标 **kui Y 向下为正**。
- 素材命名规律：金币栏 HUD 三件套 = `hud_<道具>_top/bottom/hand` + `hud_gold_glow`；
  商店/内购图集里的 `fullads_reward_*` 是**商店图**，别当特效素材（`gui_common` 里才有真帧）。
- ⭐⭐⭐ **多帧"拼接装饰"（框/条/边）的相对位置，一定从共用画布反推，别目测**：
  KR3 的两条金边两帧都声明 `size={282,126}`，只差 `trim`：上框 `trim.y=37`、下框 `trim.y=66`
  ⇒ 真实相对位移 **29px**，且互相**压 6px**；合起来 144×61、中间留 120×23 的窗口。
  按 trim 差摆 → 一次就对；自己拍一个 `FBOT_Y` 就会把两条边拉开 130px（2026-10-21 实机翻车）。
  同理 `.exo`/图集里"半截特效"的偏移也都写在 trim 里。
- ⚠ kui `Label` **没有 outline** 属性：要在花哨背景上保证可读性，只能叠两层同文本
  label（暗色 +1/+1 偏移当描影），两层都要在 `update_hud` 里同步改文字。

### 由此带来的入口位置问题 → **改为复用本体入口 + 页面 tab**（2026-10-17 用户定案）
- 官方「法术」按钮 `self.spell_button`（screen_map.lua:781）**占用的正是本插件入口的老位置**
  `original_cat_filter_pos` = `h_button.pos.x - 170`（:643-646 / 769-773）。
- 而「切换地图」已**居左对齐屏幕边**（`footer_left`，:748-750）⇒ 旧算法
  `_change_btn.pos.x - 170` 直接把入口甩出屏幕（用户截图"只剩一点点"）。
- 中途做过一版"放法术按钮正上方"（`v(ref_x, ref_y - (ref.size.y + 2))`）—— **已被取代**：
  用户明确要求「**复用本体的入口，在本体的法术选择页面添加页面切换，表明是：插件法术**」。
- **现行方案**（`kr6_powers_room.lua`）：
  · `try_install` 见 `sm.spell_button` ⇒ **不挂自建按钮**（并摘掉旧的），`return true`
  · `ensure_spell_tab_hook` = 惰性 `HOOK(sm, "ensure_spell_view")`（幂等 `_kr6_spell_tab_hooked`），
    本体法术页首次创建时注入
  · `inject_body_tabs(view, sm)` 往 `view.back` 左上 `(30,14)` 挂两个 tab：
    **官方法术 / 插件法术**，当前页用 `heroroom_selectBtn_0003/0004`（选中组）、另一颗 `0001/0002`
  · 点「插件法术」→ `view.hidden = true` + `M.open_room(sm, view)`；
    插件页顶部的 tab 点「官方法术」→ `room:dismiss()` + `from_view.hidden = false` + `:enable()`
- ⚠⚠ **`hidden = true` 本身阻断输入**（`lib/klove/kui.lua:736` `if self._disabled or self.hidden`）
  ⇒ 切页只改 `hidden`，不要额外 disable。
- ⚠ **切页别用 `PopUpView:hide/show`**（带 tween+timer，不是 tab 手感）⇒ 直改 `hidden`。
- ⚠ 全库**没有专门的 tab 帧**（934 个含 "tab" 的全是 tabla/table 贴图）⇒ 用
  `heroroom_selectBtn_0001~0004`（本体 hero 选择按钮，两组状态正好当"未选/选中"）。
- ⚠⚠ **GUI 无法离线实例化**（`GGButton:new` 报 "Image heroroom_selectBtn_0001 not found"）
  ⇒ tab 的视觉/点击**只能实机验收**，探针只能保调用链（`inject_body_tabs` / `ensure_spell_tab_hook` /
  幂等键 / 素材帧名 / 本地函数顺序）。

## 11. ⭐⭐⭐ 本体更新会**删帧** —— 排查与自保（2026-10-17 `power_button_mask` 血案）

### 症状
进关卡（不是局外）就崩、插件被自动禁用：
```
lib/klove/kui.lua:529: attempt to index local 'ss' (a nil value)
  kui.lua:529 set_image → :491 initialize → :1126 initialize
  all-desktop/game_gui.lua:2428 initialize          ← 本体基类
  kr6_powers_buttons.lua:49 initialize → :223 add_buttons
kui.error set_image() - Image power_button_mask_0001 not found in database
```
**看到 `set_image ... not found in database` + `ss nil` = 硬编码帧名在新版本体里没了。**

### ⭐⭐ 排查方法论：索引重建 + 新旧 diff（比人工猜快得多）
```bash
cp .workbuddy/_krab_index.json .workbuddy/_krab_index.old.json
python .workbuddy/_krab_check.py --rebuild    # 从 KingdomRushDove/_assets 重扫 KRAB
python .workbuddy/_diff_idx.py                # 列出被删帧 + 体检插件引用的本体帧
```
- ⚠⚠ **旧索引不可信**：本体更新后 `_krab_index.json` 仍保留**已删除**的帧 ⇒
  直接查索引会得出"帧存在"的错误结论（本次 `power_button_mask_0001` 就是如此）。
- 本脚本会抓插件源码里 `in_game_icon_*` / `mapButtons_*` / `power_button_*` 三类硬编码帧，
  逐个报 `ok` / `MISSING(new)`。

### 本次结论（本体 2.0.9.5）
- 删了 **46 帧**：`power_button_mask_0001~0028` + `power_button_icons_*`
  （新源码里 `power_button_mask` **零引用** ⇒ 本体自己也不用这批了）。
- 插件引用的 5 个 `in_game_icon_power_*` + 2 个 `mapButtons_notxt_001*` **全部健在**。

### 自保范式：**把外部帧名收进一处 + 过 sprite_exists 守卫**
```lua
-- 传帧名给**本体基类**之前必须探测（本体基类不做守卫，缺帧直接 KImageView:new 崩）
local mask_frame = sprite_exists(FRAME_INACTIVE) and FRAME_INACTIVE or nil
super.initialize(self, def.icon, mask_frame)
-- frame 为 nil ⇒ 基类 `if mask_image then` 跳过创建 ⇒ 少个装饰件，但绝不崩
```
- `sprite_exists` 用 `require("lib.klove.image_db"):s(frame)` + pcall（别用 `I:exists` 之类猜测）。
- ⚠ **优先用自家图集帧**（`kr6_power_ui` 随插件加载、版本自控），不要用本体帧做"非可选装饰"。
- ⚠ 死字段清理：`SpellTable[*].mask` 在改为内部常量后**删掉**（否则两个帧名来源必不同步），
  首处留注释说明为什么删，防后人加回旧帧名。
- 探针要加三条：**代码里零引用旧帧** / **不再把 `def.mask` 传基类** / **传参前过 sprite_exists**。

## 12. ⭐⭐⭐ 本体现在也有 KR6 法术音效 —— **同名 key 会把插件的音效全部饿死**（2026-10-17 用户实测）

### 症状
```
sound_db.error play() - SOUND PowersMusketeersSummonTaunt defined but sound sources missing. Missing file during load?
sound_db.error play() - SOUND PowersRoyalDecreeCastLvl6 defined but sound sources missing.
```
（`KR6PW_` 前缀出现前的旧症状；日志只报**第一次**碰到的 id，因为 `missing_sources_warned` 会去重）

### 根因链（必须按这个顺序读才通）
1. **本体 2.0.9.5 自带整套 KR6 法术**：`kr1/spell_system.lua:25 SPELLS.module_names` 九个
   `kr1.spells.*`，每个有 `M.required_sounds`（`{"spell_musketeers"}` 等），
   `_assets/kr1-desktop/sounds/sounds.lua` 里 `Powers*` **37 个 key**，
   插件 17 个音效里有 **16 个撞名**（只有自己改过名的 `KR6ReinforcementTaunt` 幸存）。
2. **本体那批组只在"选中本体法术"时加载**：`all/director.lua:510-518`
   `local spell = SPELLS:get_selected(); if spell then load_sound_groups(spell.required_sounds) end`。
   玩家选的是**插件**法术 ⇒ `get_selected()` 为 nil ⇒ `spell_musketeers` 组**永远不加载**。
3. **`sound_db.sources` 用文件名当 key**（`all/sound_db.lua:328 self.sources[fn] = {master_src}`），
   且 `source_uses[fn]` 按**文件名**做引用计数去重（`:257-264`：`if self.source_uses[fn] then +1 else 加载`）。
   本体 `sounds.lua` 的 `files` 是**裸文件名**，我们以前塞的是 `"../../../plugins/..."` ⇒ key 不同、各自创建。
4. **致命写法**：`for id in pairs(SOUND_DEFS) do if not S.sounds[id] then ...`
   —— 本体已定义同名 id ⇒ **整条跳过**，既不建自己的 sources 也不改 `sounds[id]`
   ⇒ 播放时用本体那份裸名 `files` ⇒ `sources[fn]` 为空（组没加载）⇒ `n_ps == 0` ⇒ 报错。

### ✅ 修法（两层都要做，缺一层就静默无声）
```lua
-- ① config 里集中放两个常量（不要在 lua 里散落字面量）
SFX_ID_PREFIX   = "KR6PW_",                      -- sound id 私有前缀
SFX_PATH_PREFIX = "../../../plugin_kr6_powers/", -- sources key 前缀（避开裸名去重）

-- ② 注册：id 与判断条件**都**换成 priv_id
local priv_id = C.SFX_ID_PREFIX .. id
if not S.sounds[priv_id] then
    for _, f in ipairs(sd.files) do
        local source_key = C.SFX_PATH_PREFIX .. found   -- 绝不能是裸名
        ...
    end
    S.sounds[priv_id] = { files = files, ... }
    S:_precache_sound(priv_id, S.sounds[priv_id])        -- 别只靠 queue 时懒补
end

-- ③ 模板侧统一出口，别散写字符串
function M.sfx(id) return C.SFX_ID_PREFIX .. id end
tt.sound_events.insert = M.sfx("PowersMusketeersSummonTaunt")
```

### ⚠⚠ 为什么不能"只在撞名时才改名"
`source_uses` 是按**文件名**去重的，跟 id 无关：只要本体任何组先加载过同名 ogg，
sources 里就只剩本体那条路径的 entry。所以 **path 前缀必须永远带**，
不能指望"我改的 id 不撞名就不会有事"。反过来，id 前缀也必须永远带 ——
否则将来本体再加一个同名 key，你又会静默失声。

### ⚠ 为什么不能粗暴 `S.sounds[id] = 我的定义`
那会**直接顶掉**本体的法术音效（玩家选本体法术时声音就变了/错了）。
前缀是唯一既修好自己、又零影响本体的写法。

### 探针必须有的三条（否则假绿）
1. **全库扫模板 sound 字段**：`E.entities` 里所有 `kr6_powers_*` 的
   `sound_events.* / sound / timed_attacks` 递归找 `Powers*` 裸名 ⇒ 必须 0 个。
   （比逐个模板点名强：漏一处 `M.sfx()` 包装就是一条静默无声的字段。）
2. **源码正则断言注册逻辑**：`not S.sounds[priv_id]` / `S.sounds[priv_id] = {` /
   `C.SFX_PATH_PREFIX` 三处都在（防有人改回去）。
3. **前缀化后与本体零交集**：从本体 `sounds.lua` 抽出 `(\w+)={files=` 的 key 集合，
   断言 `P..k` 不在其中。
- ⚠ 负向自测必做：把某一处 `M.sfx("...")` 还原成裸名字符串 ⇒ 断言 1 应精确点名该模板。

## 13. ⭐⭐ 把「独立法术插件」并入本插件 —— `on_cast` 范式（2026-10-17 迪纳斯合并）

### 何时该合并
两个插件都有「局内法术按钮」时，往往在**重复造同一套轮子**：
按钮类、指针注入、热键、点地图选点、HUD 挂载、配置面板。
判据：`grep -n "HOOK("` 两边一看，重复 3 个以上 hook 就该考虑合并。

### ⭐ 核心：本插件的法术有两种施法形态
| 形态 | 特征 | 实现 |
|---|---|---|
| **控制实体型**（火雨/援军/索罗/火枪手/号令） | 先建一个 control 实体，由它的脚本去施放 | `def.control_template` |
| **即时召唤型**（迪纳斯） | 直接 `create_entity(单位模板)` + `queue_insert` | `def.on_cast(store, wx, wy)` |

```lua
-- kr6_powers_spells.lua 的 M.cast 里，on_cast 分支**必须排在 control_template 之前**
if def.on_cast then
    return def.on_cast(store, wx, wy) and true or false
end
local e = E:create_entity(def.control_template)
```
⚠ 顺序反了会先建一个不必要的控制实体（轻则浪费，重则 script 报错）。

### 并入清单（照着做不会漏）
1. **新建 `<plugin>_<feature>.lua`**：`register_templates()` / `can_select()` / `spawn()`
2. **原插件的 hook 逐一映射**，能删就删：
   - 按钮类 → 复用 `Kr6PowerButton`
   - HUD 挂载 → 复用 `add_buttons`（别再用 `HudBottomView.powers` + `power_buttons`，
     那套是"本体 power 按钮"的注册表，两套会打架）
   - 指针 → 复用 `inject_pointers`（`POINTER_ICONS` 加一项）
   - 热键 → 复用 `HOTKEYS`
   - 选点 → 转成 `can_select()` 挂到 SpellTable
3. **SpellTable 加条目** + i18n 加 `KR6_POWER_<ID>_NAME`
4. **配置 8 项 → 六处联动**（值表 / key_order_list / key_label_map / DEFAULTS / apply / README）
5. **资源跨关**：原插件若依赖某关卡的纹理/音效组，必须自己
   HOOK `load_texture_groups`（**在 next() 之前追加**）+ `load_sound_groups`
6. **旧插件必须移走**（不是禁用就行）：两版会重复注册同名模板 / 重复改写同一模板的 `main_script.update`
7. **备份再移**：`cp -r` 到 `.workbuddy/backup/<name>_<side>_<date>`，方便回退

### ⚠ 两个必踩点
- **图标帧**：并入方常用本体帧（如 `kr3_hero_portraits_*`），无法加 `kr6p_` 前缀 ⇒
  探针的"全前缀"规则会红。要么把像素搬进自己图集，要么**显式白名单 + sprite_exists 守卫**，
  并在注释里写清为什么可以例外。
- **`add_buttons` 建按钮前必须 `sprite_exists(def.icon)`**：图标帧缺失时
  `KImageView:new` 会直接崩在 `kui.lua:529`，而不是"少个按钮"。

## 14. ⭐⭐⭐「上限值是几」这种常量最容易只改一处 —— 静默丢数据（2026-10-18 开放 6 选）

### 症状
局外能选 6 个、界面也显示 6 个槽位，但**一进关卡只剩 3 个按钮**，日志完全干净。

### 真因
"最多带几个"被写在**三个互不相干的地方**，它们之间没有任何运行时校验：

| 位置 | 常量 | 漏改的表现 |
|---|---|---|
| `<plugin>_store.lua` | `M.MAX_SLOTS` | **读档时 `#out >= MAX_SLOTS` 截断** ⇒ 前面全对，进关才丢，且零报错 |
| `<plugin>_room.lua` | `local SLOT_COUNT` | 局外只画得出 3 个槽位（选不上第 4 个） |
| `<plugin>_config.lua` | `SELECTED` 上限注释 | 只是文档，但会让人以为改完了 |

⚠ 最阴的是 `store.MAX_SLOTS`：前两处改了之后**操作层面完全正常**，
只有跨过"存档 → 进关读档"这条边界才暴露。

### ✅ 探针必须把三处绑在一起
```lua
local Store = require('<plugin>.<plugin>_store')
ck('store.MAX_SLOTS == 6', Store.MAX_SLOTS == 6)
local sc = room_src:match('local SLOT_COUNT = (%d+)')
ck('room.SLOT_COUNT == 6', sc == '6')
ck('两处一致', Store.MAX_SLOTS == tonumber(sc))
```
同类的还有：`BTN_PER_ROW` 必须能整除总数（否则出现半排）。

### 顺带：九宫格面板的"可用宽度"不是面板宽度
```lua
-- ⛔ 错：拿 W=920 当可用宽
-- ✅ 对：减去左右边框
--   GG9View 的 slice_rect = r(左厚, 上厚, 中列宽, 中行高)
--   可用宽 = W - 左厚*2   （本例 920 - 57.6*2 ≈ 805）
```
本例 6 个槽位：`6×124 + 5×12 = 804 ≤ 805` 刚好塞下，**GAP 从 36 压到 12**。
⚠ 面板高度往往已贴近屏幕极限（本例 752 vs 768）⇒ **加高不是选项**，
横向塞不下就只能缩尺寸或缩间距。

---

## 15. ⭐⭐⭐ 跨版本移植：从 KR5 Alliance 搬兵种/法术（2026-10-18 王国骑士首次跑通）

> 前面 1~14 节都是 **KR6 Genesis**；本节是**换源版本**时的增量经验。
> 首个案例：KR5 Alliance 的叛军民兵 `rebel_militia` → Dove 法术 `kingdom_knight`（王国骑士）。

### 15.1 源目录与反编译（KR5 Alliance，LuaJIT 字节码 `\x1bLJ`）

```
<KR Alliance>/kr5/data/balance/balance.lua          # 数值总表（upgrades.* / reinforcements.*）
<KR Alliance>/kr5/upgrades.lua                       # 升级树节点（含 blocks 互斥字段）
<KR Alliance>/kr5/scripts_game.lua                  # 行为脚本（2.9MB，反编译约 2s）
<KR Alliance>/kr5/templates_game.lua                # 实体模板（2MB）
<KR Alliance>/kr5/data/animations/all/game_animations_new.lua   # 动画段（from/to 定义在这）
<KR Alliance>/_assets/kr5-desktop/images/ipad/go_commons.lua    # 图集帧表（+ go_commons-1.png）
<KR Alliance>/_assets/kr5-desktop/images/ipad/gui_common.lua    # UI 图集（图标/指针）
<KR Alliance>/_assets/kr5-desktop/strings/en.lua                # 文案（键值对可直接抽）
```

⚠ **反编译器只在自身目录写 `./output`**（不看 cwd）⇒ 并行跑要 `cp luajit-decompiler-v2.exe <子目录>/` 再 `cd` 进去。
⚠ 实测 **2~2.9MB 文件约 2 秒**，比"265KB 要 2 分钟"的旧印象快得多 —— 不要因为怕慢就不敢反编译大文件。

### 15.2 ⚠⚠⚠ 图集 `alias` 陷阱：偶数帧可能根本没有 quad

KR5 图集里 **一半的帧是别名条目**，形如 `reinforcements_lvl3_01_0018 = { alias = {...} }`，
**没有 `size/trim/f_quad`**。直接按 `f_quad` 过滤只能拿到 66/116 帧。

- 判据：`grep -c "前缀_"` 的次数 ≠ 带 `f_quad` 的条目数；缺的号恰好是偶数。
- 做法：**以奇数帧为真实条目，`alias` 指过来的偶数帧照抄奇数帧的 quad**（视觉上两帧相同）。
- 解析器必须**手写括号计数**：非贪婪正则 `\{(.*?)\}` 会被内层 `{ ... }` 提前截断
  （症状：条目数少一半、字段抓不到但不报错）。

### 15.3 动画段从哪来

不要猜 idle/walk/attack/death 的帧区间 —— 反编译 `data/animations/all/game_animations_new.lua`，
搜 `<贴图前缀>` 就能看到 `from/to`。本例 `reinforcements_lvl3_0X`：
`idle 1` / `walk 2-17` / `attack 18-39` / `death 40-58`（两种外观**段位完全一致**）。

### 15.4 ⚠⚠ 死旋钮：面板暴露了 ≠ 模板真读了（这次一次抓出 2 个）

新建数值段时最容易漏的**落点字段名**（我第一版两个都写错）：

| 面板/balance 键 | 正确的模板落点 | 错误写法（改了没反应） |
|---|---|---|
| `spiked_armor`（反伤） | **`tt.health.spiked_armor`**（`kr1/enemies.lua:15434` 是范例） | 只写进 balance，模板没接 |
| `damage_factor`（伤害倍率） | **`tt.unit.damage_factor`**（援军同款 `spells.lua:331`） | 同上 |

**通用探测法（强烈建议每个新数值段都跑）**：把每个面板键逐项设成一个可识别的新值 →
`S.save` + `S.apply`（会 re-register 模板）→ 断言**模板字段**真的变成那个值。
输出形如 `⑩ 12 项面板键全部有消费点（无死旋钮）`，漏一个就 `11/12` 并打印 `<旧值 ~= 新值>`。

### 15.5 新法术接入的 7 个触点（漏一个就静默残废）

1. `kr6_powers.lua` 的 `ATLAS_NAMES` 加新图集名
2. `kr6_powers_spells.lua`：动画表 + `register_animations` + 模板（control / soldier / hit_fx）+ `SpellTable[id]`
3. `kr6_powers_balance.lua`：`B.<id>` 字面量段 + `apply()` 里的逐键 `num(cfg, ...)` 行
4. `kr6_powers_config.lua` **三件套**：字面值 / `key_order_list` / `key_label_map`
5. `kr6_powers_settings.lua`：`FLAT_PATHS` + `PERCENT_KEYS`（0~1 比例字段）+ `SPELLS` 卡片
6. `kr6_powers_buttons.lua`：`POINTER_ICONS[id] = "kr6p_xxx"`（**必须自家前缀**，复用别法术的会被探针拦）
7. `kr6_powers.lua` 的 `SPELL_NAMES`：`KR6_POWER_<UPPER_ID>_NAME`（列表/槽位/信息条共用）

⚠ 士兵还要额外设 **`tt.info.i18n_key`**：信息条名字 = `_(info.i18n_key.."_NAME")`，
不改就一直显示**基类**（本体民兵）的名字。

### 15.6 探针坑（这次全踩了一遍）

- **`animation_db` 是位置式结构**：`A.db[name] = { frame_count, prefix, nums }` ⇒ 帧数是 **`a[1]`**，
  不是 `a.frame_count`（nil ⇒ 所有帧数断言假失败）；`nums` 下标**从 0 起**。
- **必须给 storage 打桩**：`storage.load_lua/write_lua` 指到内存表，否则「改值→apply」那段
  会写真实 `game_params.lua`（离线报 `storage.error Error writing game_params`，还可能污染玩家存档）。
- **恒真断言自查**：`xxx or true`、对字符串键表取 `#`、只测单实例不测实例间隔离 —— 都等于没测。
- **有效性验证**：写完探针必须**注入原 bug** 确认真的 FAIL 再还原。本次两个注入：
  `armor = 40`（忘了 0~1）⇒ 三件套探针抓；删掉 `spiked_armor` 那一行 ⇒ 死旋钮探针抓。
- ⭐ **三件套分叉是正确行为**：注入 balance 字面量后「运行时值」断言**仍过**是对的 ——
  运行时值来自 `config.lua`（经 apply），面板默认值来自 balance 字面量，两者不一致正该由 triplet 探针抓。

### 15.7 两套输入机制不能混用（安卓血案）

桌面的数值输入靠自身 `_editing` + 键盘输入；**安卓走本体 `sm.numeric_keyboard`（`screen_map.lua:916`）
独立弹窗** `open(initial, cb, opts)`。安卓分支**绝不能设 `_editing`** ——
`Stepper:update` 会把它当"本地编辑中"，每帧把显示刷成 `_edit_text.."|"`（空串）⇒ 数字变空白，
玩家看到的就是"点了数值没法输入"。

另：面板"每帧提到顶层"的守卫会让**刚弹出的键盘又被压回面板下面**（表现为"没反应"，
退出页面才发现键盘躺在底下）⇒ 期望顺序必须是「其他视图 → 面板 → **可见弹窗**」，
判定弹窗是否开着用 `not c.hidden`（`PopUpView:show()` 末尾才置 false）。

### 15.8 候选池 vs 槽位

候选数可以**多于**槽位数：`room:add_spell` 里 `#selected >= SLOT_COUNT` 就提示"满了"，
所以"7 个候选 / 最多选 6"不用改任何逻辑，只加 `SpellTable` 条目即可。
默认不装 = **不要**往 `config.SELECTED` / `SELECTED_DEFAULT` 里加。

### 15.9 ⚠⚠⚠ 「取满级数值」不只是数值 —— 还包括**满级才有的额外单位/形态**

2026-10-18 返工案例：王国骑士第一版只搬了 `rebel_militia` 的基础 2 兵，
**漏了满级节点 `power_trio` 额外召唤的那名大骑士**，用户当场指出。

⇒ 移植前必须把**升级树走完**，把"满级"理解成：
1. 数值取满级（已知）
2. **满级解锁的额外单位 / 阵型变化 / 附加效果也要一并实现**
3. 反过来说：升级树里**互斥支线**只能选一条（本例 `rebel_militia` vs `shadow_archer`），
   而**同一支线的终极节点必须包含**（本例 `power_trio`）

KR5 叛军线实例（可直接照抄结构）：

| 节点 | 效果 | 移植处理 |
|---|---|---|
| `rebel_militia` | 普通兵换成重甲民兵（hp 100 / armor 0.4） | 基础单位 |
| `power_trio`（王国楷模） | 额外召 **1 名骑士楷模**，3 个单位改椭圆三等分 | **必须加**，恒定生效 |
| `shadow_archer` 整支 | 另一条互斥支线 | 不做（另立法术） |

### 15.10 ⚠⚠ 断言几何前先读引擎 helper —— `point_on_ellipse` 有 `aspect=0.7`

```lua
-- all/utils.lua:278
function U.point_on_ellipse(center, a, angle, aspect)
	aspect = aspect or 0.7
	return V.v(center.x + a * cos(angle), center.y + a * aspect * sin(angle))
end
```

**y 方向被压扁 0.7** ⇒ 三点到落点的欧氏距离**不相等**（半径 30 时实测 25.20 / 29.74 / 22.18），
"两两夹角 120°"也不成立（2.33 / 2.17 / 1.79 弧度）。

我按教科书圆的几何写断言 ⇒ 5 条**假 FAIL**。正确做法：**用引擎同一公式反算期望坐标**再逐点比对
（顺带把 `index` 分配也验了）。Alliance / KR6 的布点代码用的就是这个函数，所以实现本身没问题。

⚠ 同类风险：`U.point_on_circle`、`U.point_in_ellipse`……凡带 `aspect` / 仿射参数的 helper，
   **先看实现再断言**。

### 15.11 图集提取用参数化脚本（别再写一次性脚本）

`.workbuddy/kr5_analysis/extract_kr5_atlas.py` —— 改 `SPECS` 表加一条就支持新单位：

```python
dict(src_prefix="reinforcement_linirea_lvl_5_unit_",
     frame_count=104,
     out_name="kr6p_kk_big",
     anim="idle 1 / walk 2-25 / attack 26-60 / death 61-104",
     note="...")
```

它会：① 手写括号计数解析图集 ② **自动把 alias 条目补成实帧**（否则少一半帧）
③ shelf 打包成 2048 宽图集 ④ 生成 `kr6p_*` 前缀的 lua（含 a_name/size/trim/f_quad）。
⚠ `out_name` 必须 `kr6p_` 开头（探针强制自家前缀，防 `db_atlas` 抢帧）。

### 15.12 ⚠⚠⚠ 三个「模板/脚本一写就崩」的硬点（2026-10-18 暗影弓手实战）

**1. `decal_scripted` 只带 `main_script`**（`all/templates.lua:65-66`）
飞行仆从（乌鸦/鹦鹉这类无血量体）继承它之后**必须显式补组件**，否则下一行设字段就崩：

```lua
tt = E:register_t("kr6p_crow_entity", "decal_scripted")
E:add_comps(tt, "force_motion", "melee")   -- ← 漏了这句
tt.force_motion.max_a = 1200               -- attempt to index field 'force_motion' (a nil value)
```
⚠ 报错发生在 `register_templates()` 里 ⇒ **整个 E.Load 链失败**，表现为"所有法术都没了"，
  而不是"只有乌鸦不对"。看到某个新模板报 nil 字段，先查它**基类有没有那个组件**。

**2. 脚本函数里的 `U` / `S` 不是全局**
插件注入的全局只有 `E`（部分环境还有别的），`U` / `S` **必须自己 require**：

```lua
M.crow_update = function(this, store)
	local U = require("utils")
	local S = require("sound_db")
	local E = rawget(_G, "E")
```
⚠ 漏了的表现极具迷惑性：协程**第一帧就崩**，实体根本不出现 ⇒ 看着像"没召出来/动画错"。

**3. 远程士兵的 `damage_min/max` 要写在**攻击层**，不能只写 bullet**
```lua
tt.ranged.attacks[1].damage_min = ...   -- ← 信息面板 get_info 读这两个
tt.ranged.attacks[1].damage_max = ...
tt.ranged.attacks[1].bullet = "..."     -- bullet 上的伤害只影响弹丸本身
```
漏了 → 士兵信息面板远程伤害显示空白（探针报 `<nil>`）。

### 15.13 乌鸦类「环绕 + 扑咬」仆从的最小实现

Dove 自带 `force_motion` 组件 + `U.force_motion_step`（加速度模型），不用自己写物理：

```lua
-- 无目标：绕主人在 y+flight_height 的高度做椭圆环绕
orbit_phase = orbit_phase + this.orbit_speed * store.tick_length
local ang = (this.crow_id * math.pi + orbit_phase) % (2 * math.pi)   -- 两只差 π
local dest = U.point_on_ellipse(V.v(owner.pos.x, owner.pos.y + this.flight_height),
                                this.orbit_radius, ang)
U.force_motion_step(this, store.tick_length, dest)

-- 有目标：飞到 target.pos + 固定偏移，进入 range 就咬
local d = SU.create_attack_damage(a, target.id, this)
store.damage_queue[#store.damage_queue + 1] = d
U.animation_start(this, "attack", target.pos.x < this.pos.x, store.tick_ts, 1)
U.y_wait(store, a.cooldown)
```

要点：
- `U.find_nearest_enemy(store, owner.pos, 0, target_range, a.vis_flags, a.vis_bans)` 索敌（以**主人**为圆心）
- `queue_damage` 是**文件内局部函数**，插件里等价写法是往 `store.damage_queue` 追加
- 生命周期完全绑主人：`owner.health.dead` 或 `owner.reinforcement.ts + duration` 到期 ⇒ 播 death 后删
- 反向通信（主人抬手）：乌鸦设 `owner.raise_arms = true`，主人 update 里读，配合 3s 冷却
- ⚠ `decal_scripted` **没有 health** ⇒ 不能对乌鸦用 `health.dead` 判自己死

### 15.14 探针里真驱动协程（测"看得见的行为"而不是"函数存在"）

`update` 是协程时，静态断言只能证明"注册了"。要证明**真的会动**：

```lua
local store = { tick_ts = 1, tick_length = 1/30, entities = {}, damage_queue = {},
                pending_inserts = {}, pending_removals = {} }
-- ⚠ simulation:queue_* 内部用 self.store（all/simulation.lua:222-250）⇒ 必须打桩
local prev = require('simulation').store
require('simulation').store = store

local co = coroutine.create(function() Spells.crow_update(crow, store) end)
for _ = 1, 12 do
	store.tick_ts = store.tick_ts + 1/30
	assert(coroutine.resume(co))                       -- 不崩
end
assert(math.abs(crow.pos.x - x0) + math.abs(crow.pos.y - y0) > 1e-4)  -- 真的位移了

-- 再把 owner 标死，跑到协程 dead，证明"会自己散场"而不是无限循环
```
⚠ 不打桩 `simulation.store` 会报 `attempt to index local 'd' (nil)` —— 是**探针环境问题**，
  别误以为是脚本 bug。

### 15.15 「取满级」= 把整条升级树走到头（含**外观**与**已有数值的修正**）

暗影弓手这次顺带修正了王国骑士：叛军线是
`rebel_militia → thorny_armor → power_trio`，而 `thorny_armor`（`upgrades.lua:930-940`）
**同时**改了贴图（`reinforcements_lvl3_0X` → `lvl4_0X`）和 `spiked_armor = 0.2`。
⇒ 上次只搬「终极节点额外单位」是不够的，**中间节点的副作用也会改变外观/数值**。

检查清单（换版本移植时逐条走）：
1. 分支起点 → 终点，**每一级**的 `upgrades.lua` apply 块都读一遍（改了什么字段）
2. 有 `render.sprites[1].prefix = ...` 的 ⇒ **满级要换图集**
3. 有 `t.health.*` / `t.ranged.*` 赋值的 ⇒ 满级数值不是 balance 第一层的值
4. 改完 **balance 与 config 两处都要改**（运行时值来自 `config.lua`，只改 balance 不生效）

---

## 16. ⭐⭐⭐ 从「plist 引擎」（KR4 Vengeance / KR2 等）搬法术：配置是**分层对象**（2026-10-19 灵魂冲击血案）

> ⚠ 本节记录的方法论仍然有效，但**灵魂冲击这个法术已于 2026-10-19 按用户要求从 `kr6_powers` 整体移除**
> （代码/素材/面板项/README 全清）。下次再搬 plist 类法术时按本节流程走，别以为它还在。

KR4 不是 love 引擎，法术定义在 `Settings/power_settings.plist`（XML 明文），动画在
`Animations/Powers/*.plist`，贴图在 `Sprites/HD/...` 的 TexturePacker 图集里。

**核心教训：只搬最外层两层 = 残缺版。**

`power_soul_impact` 的实际结构（`object` 下逐键）：

| 层 | 键 | 视觉 | 帧 |
|---|---|---|---|
| 施法主体 | `effect` | 光柱下落（`soul_impact`） | 16 |
| 落点爆炸 | `explosion` | 聚能 → 爆裂 → 余晖 | 38（第 39 帧是 3×3 空白，丢弃） |
| 地面残骸 | `explosion.fx_with_delay` | `decal_crater` 单帧 | 1 |
| **追敌灵魂** | `call_damned.proyectile` | 绿球飞出 + `bolt_hit` 命中四散 | 1 + 12 |
| **弹道拖尾** | `call_damned.proyectile.particle` | `bolt_particle1/2` | 10 + 10 |
| 眩晕 | `soul_shockwaves.modifiers` | `stun_animations.plist` | 复用本体 |
| 减速 | `fear_damned` | 无独立动画 | — |
| 回响 | `soul_echoes` | 复用整套 | — |
| 风暴 | `soul_storm.extra_effects` | 复用整套 | — |

第一版只做了 effect + explosion + decal ⇒ 用户原话「**至少缺失 90% 特效**」。
真正撑起观感的是 `call_damned`（4 个绿魂四散追敌）。

**移植检查清单（plist 类法术）**
1. `plistlib.load` dump 整个 `power_<x>` 块**逐键展开**（含嵌套），别只读 `cooldown/damage`；
2. 每个 `animations_file` 指向的 plist 都读一遍，`prefix + fromIndex/toIndex` 就是动画段；
3. `TexturePacker v3` 字段：`textureRect` / `spriteSize` / `spriteSourceSize` / `spriteOffset` / `textureRotated`
   - ⚠⚠⚠ **`textureRotated=true` 时 `textureRect` 的 (w,h) 是「未旋转」尺寸，图集里实际横躺占 `(h, w)`**
     ⇒ 正确裁法 `atlas.crop((x, y, x + h, y + w)).transpose(ROTATE_90)`。
     按 `(w,h)` 裁只拿到左上角一小块 + 再 `resize` 回 `(sw,sh)` ⇒ 变成"一根两像素宽的细线"
     （2026-10-19 灵魂冲击光柱血案，用户原话「就几个两像素宽的条」）。
     ⇒ **`cut()` 必须有 `if img.size != (sw, sh): raise`**，宁可报错也不许静默 resize。
   - `trim` 由 offset 反推：`left=(srcW-w)/2+offX`、`top=(srcH-h)/2-offY`（y 向上为正）
4. 画布尺寸差异大（光柱 140×636 / 爆炸 516×644）⇒ **各自 anchor 按内容中心算**，别统一拍脑袋；
   原版写了 `anchor` 就直接抄（灵魂冲击的爆炸就是 `{0.5,0.5}`，我曾猜成 0.28 ⇒ 整体抬高 ~100px）；
5. 素材基准 1080 ⇒ 渲染统一 ×`0.7111`（同 KR6 口径）。

**动态特效实体的模板套路（Dove 侧）**
```lua
-- 单帧（绿球本体）：animated=false 时 render 不拼 prefix ⇒ name 必须写完整图集帧名
tt = E:register_t("kr6p_si_bolt", "decal_scripted")
tt.render.sprites[1].name = "kr6p_si_bolt_0001"
tt.render.sprites[1].animated = false

-- 一次性动画（命中/粒子）：animated=true + loop=false，脚本里 U.y_animation_play(this,"run",...) 等它播完
tt = E:register_t("kr6p_si_hit", "decal_scripted")
tt.render.sprites[1].prefix = "kr6p_si_hit"
tt.render.sprites[1].name = "run"
tt.render.sprites[1].loop = false
```
- 飞行体不用 `force_motion`（那是物理模型，落点不可控）⇒ **协程里 lerp + `sin(πt)*arc` 上抛**，
  到点结算伤害 + 生成命中特效 + `queue_remove_entity(this)`；
- 拖尾粒子：飞行循环里按 `puff_interval` 累加 `store.tick_length`，spawn 时
  `pf.render.sprites[1].prefix = (math.random(2)==1) and "pt1" or "pt2"` 随机两套；
- 命中判据：`store.entities[id]` 存在**且** `target.id == 目标 id`（对象池会复用）。

**离线探针要真跑协程**（照抄 `verify_kr4_si` ⑧）：
- 打桩 `simulation.store / queue_remove_entity / queue_insert_entity / systems_on_queue_unconditional_*`；
- 打桩 `U.find_enemies_in_range` 返回带 `pos` 的目标（**不带 pos 会崩在距离排序**）；
- ⚠ 离线不跑 render 系统 ⇒ `sprite.runs` 不会自增，`U.y_animation_play` 会**永远挂住**；
  要手动 `sp.runs = (sp.runs or 0) + 1/15` 模拟；
- ⚠ `da_update` 之类脚本用的 `SU`/`S` 是 plugin_globals 注入的全局，离线要 `_G.SU = require("script_utils")`。

### 16.6 ⭐⭐⭐ 「动画不动 / 定格成静态图」= `sprite.ts` 默认 0

Dove 里**脚本手动创建**的特效实体（`E:create_entity` + `simulation:queue_insert_entity`），
如果模板是 `animated = true`，必须在插入前设：

```lua
e.render.sprites[1].ts = store.tick_ts   -- 有几个 sprite 就设几个
```

原因：
- `sprite.ts` 组件默认 **0**（`all/components.lua:209`）；
- `render:on_insert_unconditional` **只在 `s.random_ts` 非空时才设 ts**（`all/systems/render.lua:231`）；
- render 每帧算 `t = (store.tick_ts - s.ts) * fps`，`tick_ts` 是关卡累计秒（几十上百）
  ⇒ `t` 巨大 ⇒ `idx = max(1, min(len, ceil(t)))` **恒等于最后一帧**。

症状不是"不播"，而是**一直显示最后一帧**（一根光柱定在那儿），特别容易被误判成"素材是静态的"。
2026-10-19 灵魂冲击连踩两轮：先怀疑素材裁错，实际是 ts 没设。

**兜底做法**（本项目 `kr6_powers` 已落地）：HOOK `systems.render:on_insert_unconditional`，
在 `next()` 之前给**本插件前缀**的模板补 `ts`（只补 `ts == 0` 的，脚本里 `U.animation_start`
已设过的不动；别对全部模板生效，避免动到本体）。

## 17. ⭐⭐⭐ 从 FL8.0（KR3 改版）搬法术：三条 FL→Dove API 口径差（2026-10-19 卫兹南之怒实测）

FL8.0 = KR3 内核 ⇒ 老引擎 API 与 Dove（KR1 内核+自家改造）**同名不同义**，逐行移植必踩：

1. **`P:node_pos` 返回值**：FL/KR3 返回 `x, y` 两数；**Dove 返回向量表**（`V.vclone(path[ni])`，
   path_db.lua:217）。`fx.pos.x, fx.pos.y = P:node_pos(...)` 在 Dove 下第二变量收 nil ⇒
   `cannot convert 'nil' to 'double'`。正确：`fx.pos = P:node_pos(pi, spi, ni)`（scripts.lua:892 同款）。
   连带：`nearest_nodes` 返回元素是 **`{pi, spi, ni, dist}` 四元组**，别 `unpack`（dist 会被当
   `return_ref`）——显式取 `[1][2][3]`。
2. **exo sprite 播放前置 `animated = true`**：`U.animation_start` 只在 `a.animated` 时才设
   `name/ts/runs`（utils.lua:389）⇒ 模板 `animated=false` 时它**什么都不做**；渲染走 else 分支
   `EXO:f(裸name)` 查 EXO.db ⇒ `Could not find exo_frame called: <name>` 刷屏。
   皇家范式（game_scripts.lua:47398）：update 里先 `sprites[1].animated = true` 再
   `U.y_animation_play(this, anim, nil, store.tick_ts)`。exo 渲染键 = `prefix.."_"..name`
   （animated 分支，render.lua:400），exo loader 注册键 = `exo_name.."_"..anim`（exoskeleton.lua:127）
   ⇒ prefix 填 exo_name、name 交给 animation_start，**模板别手设 name**。
   注意 FL 的 exo 动画名常就叫 `"anim"`（单动画骨骼），报错帧名=裸动画名是此病特征。
3. **脚本建的特效逐个设 `render.sprites[1].ts = store.tick_ts`**（insert 前）：render on_insert
   只处理 `random_ts`（render.lua:231），普通 fx `ts=0` ⇒ 恒停末帧。tween 时钟
   `ts - (tween_prop.ts or tween.ts or sprite.ts)`（tween.lua:288）⇒ 用 tween 的实体设
   `tween.ts` 即可，纯动画 fx 必须设 sprite.ts。

另：FL 的「维兹南登场」等全屏演出在 **GUI 层**（kui 视图 + GGExo），Dove 无 GGExo ⇒
全部改世界侧实体（exo decal + Z_SCREEN_FIXED 色块），blink 用协程字段直驱替代 signal。

---

## 17. ⭐⭐⭐ 从「同引擎旧作」搬兵种（KR Origins / KR2 等）：比跨引擎省事得多

判据：目标目录里有 `all/` + `lib/` + `kr<N>/` + `conf.lua` ⇒ **同一套 love 引擎**。
2026-10-19 搬 KR3 的 Elite Elves（精灵援军）实测：模板/组件/行为脚本几乎零改造。

**关键事实**
- `.lua` 仍是 **LuaJIT 字节码**（`\x1bLJ`）⇒ 用 `ljdv2/luajit-decompiler-v2.exe` 反编译；
  ⚠ 输出写在**工具所在目录**的 `output/`（不是 cwd），别找不到产物。
- 优先反编译：`kr<N>/game_templates.lua`（模板）、`kr<N>/upgrades.lua`（升级树）、
  `kr<N>/data/game_animations.lua`（动画段）、`all/scripts.lua`（行为脚本，往往与 Dove 同源）、
  `_assets/.../images/<密度>/<图集>.lua`（帧表）。
- **行为脚本先比对**：Dove 的 `scripts.soldier_reinforcement.update` 已经有 `this.ranged` 分支
  （`SU.y_soldier_ranged_attacks`）⇒ 远程援军不需要写任何新脚本。
  旧作版只多一句 `SU.soldier_courage_upgrade`（KR3/KR5 的勇气机制，Dove 没有）——直接不搬。

**两层 prefix 别混**
- 模板 `render.sprites[1].prefix` = **动画键前缀**（`soldier_re_A3` → key `soldier_re_A3_idle`）
- 动画表里的 `prefix` = **图集帧前缀**（`reinforce_A3` → 帧 `reinforce_A3_0001`）
改成插件独占前缀时**两层都要改**，且动画段的 key 必须等于「模板 prefix + "_" + 动作名」。

**远程兵的两个位置**
- 伤害在**箭矢模板**的 `bullet.damage_min/max`，`ranged.attacks[1]` **没有** damage 字段
- `E:add_comps(tt, "ranged")` 必须显式加（`re_farmer` 没有），否则永远不射箭

**图集 alias 照搬**
旧作图集 lua 的 `alias = { "xxx_0026", … }` 语义与 Dove 一致（`db_atlas[别名] = db_atlas[本帧]`）
⇒ 直接转写，帧名按 **job 的前缀映射**替换（`reinforce_proy_003` → `kr6p_re3_arrow_0003`，
不能一律 `reinforce_ → kr6p_re3_`）。

### 17.1 ⭐⭐⭐ 探针假绿：`love_stub` 把 `animation_db` 打成假表

`scripts/ci/love_stub.lua` 的 `STUB_MODULES` 里有 `animation_db` ⇒ 返回一个
「任意键返回空函数」的 stub：`A.db` 是 **function**、`rawget(A,'db')` 是 **nil**。
后果：探针里 `local b = A.db[name]` 直接报错，或写成 `if b then … end` 就**整段静默跳过**（假绿）。

✅ 正确写法（必须在 `require('scripts.ci.love_stub')` 之后、require animation_db 之前）：

```lua
package.loaded['animation_db'] = nil
package.preload['animation_db'] = nil
```

之后 `require('animation_db')` 才会加载本体 `all/animation_db.lua`，`A.db` 恢复成表。

✅ **复核结论（2026-10-19）**：现有探针（kk / sa / mk / rain / re / royal / sol / sounds / settings_e2e）
**都已经清过 preload**，没有假绿问题；只有当时新写的那个探针漏了。
⇒ 新写探针时**照抄这三行**即可，别自己另起一套。

### 17.2 ⭐⭐⭐ KR2（Frontiers）实测增量：基准分辨率 / 图标溯源 / 多别名（2026-10-19 前线援军）

**① 先定基准分辨率，再决定 scale —— 别照抄上一部作品**
`all/constants.lua` 的 `TEXTURE_SIZE_ALIAS` + `REF_H`：

| 源作 | 图集目录 | `TEXTURE_SIZE_ALIAS` | load scale | 模板 `sprite.scale` |
|---|---|---|---|---|
| KR3 Origins | `fullhd` | `fullhd = 1080` | 768/1080 = **0.7111** | 0.7111 |
| **KR2 Frontiers** | **`ipad`** | `ipad = 768` | 768/768 = **1.0** | **1.0** |

判据：`image_y`（模板顶部那个局部变量）**等于世界高度** ⇒ `image_y == 图集画布像素高` 就说明 scale=1.0
（KR2 `re_farmer`：`image_y = 44` = 画布 44px；KR3：`image_y = 54` = 76px × 0.7111）。
交叉验证：Dove 本体 `kr1/game_templates.lua:473` 的 `re_farmer` 也是 `image_y = 44 / anchor_y = 7/44`
—— 与 KR2 字面值一模一样（同为 KR1 资产族），可直接对表。

**② ⭐⭐⭐ 图标：先看 initialize 有几个分支，别只读第一个 —— 源码里 `if IS_KR3` 会坑死人**
KR2 `game_gui.lua` 的 `Power2Button:initialize` 是**双分支**：

```lua
Power2Button = class("Power2Button", PowerButton)
function Power2Button:initialize()
    if IS_KR3 then
        Power2Button.super.initialize(self, "power_button_icons_0018", "power_button_mask_0001")  -- KR3 分支
        self.animations = { default = {to=1, from=1, prefix="power_button_mask"}, ... }
    else
        Power2Button.super.initialize(self, "reinforcements_0001")                                -- ⭐ KR2 自己的
        self.animations = { default = {to=1, prefix="reinforcements"}, highlighted = {to=2}, cooldown = {to=1} }
    end
end
```

**教训**：我第一次只 grep 到 `power_button_icons_0018`（第 2299 行）就下结论，实际 KR2 走的是
第 2344 行的 `else` 分支 ⇒ 原版图标是 **`reinforcements_0001`**（`gui_common-2.png`，
**fullhd** 88 画布 / 80 内容 / trim 4；ipad 版只有 63 画布）。
高亮态是 **`reinforcements_0002`**（青色发光框）；插件按钮自带 mask 罩做高亮 ⇒ 只取 0001 即可。

⇒ 判据：**同名字符串出现多次时，先把它所在的 if/else 结构读全**
（`grep -n "power_button_icons\|reinforcements_000" game_gui_dec.lua` 一次列出所有出现点，
再 `sed -n 'A,Bp'` 看包裹它的分支）。
⇒ 另一条兜底：`grep -a -o '<关键词>[a-zA-Z_0-9]*' <图集>.lua | sort -u`
（**用语义关键词 `reinforcements`，不是代码里的前缀**）——图集里有什么才是硬事实。
⚠ 用户对"原版图标"很敏感：先扒图集、再拿图给用户确认，别用别作的同名单帧凑
（本项目曾用 KR3 的 `kr6p_re3_icon` 顶替，被用户当场指出"原版肯定是有的"）。

**③ KR2 图集 alias 是"一拖多"**：一个条目可挂多个别名
（`reinforce_B3_0007` 的 alias 列表 = `0008, 0009, 0010`；而 `0009` **不是** `0008` 的别名）。
⇒ 抽取必须建 **alias 反向表**（`alias_name → real_entry`）逐帧解析，不能按"偶数→前一个奇数"硬猜。
本项目的抽取脚本：`.workbuddy/kr2_analysis/extract_kr2_re.py`（`resolve()` + 自引用剔除 + 空帧抽查）。

**④ 施法入口可能不止 control 脚本**：KR2 的 `Power2Button:fire` 与
`scripts.power_reinforcements_control.insert` **是同款直生成**（2 个 `re_current_i`，偏移 (±10, ∓10)）
⇒ 两边都要读一遍再定 `M.<x>_control_insert`。

**⑤ ⚠⚠ 负向自测脚本别先截断再读备份**
`io.open(path,'w')` 会**立即清空**目标文件；若随后读备份抛异常（本项目：Git Bash 的 `/tmp`
≠ Windows Python 的 `C://tmp`），目标文件就被清空了（这次 `kr6_powers_balance.lua` 中招，
靠崩溃前的 `cp` 备份按 md5 复原）。
✅ 正确姿势：**先把所有备份读进内存**，再 `patch/restore` 都从内存写盘。

**⑥ ⭐⭐⭐ 对齐「某作本体」数值：真正下发的是 `upgrades.lua` 里 set_template 的模板**
援军这类可升级 power，`power_reinforcements_control` 的 insert 里建的只是 **`re_current`**
（占位模板，`E:register_t("re_current", "re_farmer")`），它的数值是**最低级**的。
Dove 在升级时才换真身：`kr1/upgrades.lua:2482`
`E:set_template("re_current", T(u.template_name))`，而
`upgrade.list.reinforcement_level_5.template_name = "re_legionnaire_ranged"`。

⇒ 查「本体满级数值」的顺序：
1. `upgrades.lua` 里找该 class 的**最高 level** 项，取 `template_name`；
2. 把该模板和它的父链读全（`RT(name, parent)` 只写**增量**字段：
   `re_farmer → re_conscript → re_warrior → re_legionnaire → re_legionnaire_ranged`，
   `hp_max / armor / damage / max_speed` 是逐级覆盖的）；
3. 远程伤害常在**弹丸模板**（`spear_legionnaire.bullet.damage_*`），不在 `ranged.attacks[1]`；
4. 回血：本体 `regen` 只有 `regen.cooldown`（结算间隔 1s），**没有 `regen.health`** ⇒ 不回血。
   KR2 的同名模板有 `regen.health = 15` ⇒ 对齐本体时必须把面板值改成 **0**。

⚠ 对齐后要同步 6 处：balance 字面量 / config 默认值 / settings / README 表 / 探针期望值 /
check 脚本；⚠ 探针**死旋钮表**的测试值若恰好等于新默认值 ⇒ 断言恒真，必须换一个值
（本项目 `duration` 23 撞车，改成 26）。

**⑦ 图标大小微调：`def.icon_zoom` + 绕中心补偿**
`kr6_powers_buttons.lua` 的 `_draw_self` 里合成两种缩放，**锚点语义相反**：

```lua
local fill  = M.icon_fill_zoom(self.size)   -- 小帧→108：必须从原点长（长到 [0,108] 与框同心）
local extra = def.icon_zoom or 1            -- 法术自定义：必须绕中心
local zoom  = fill * extra
local c     = self.size.x * fill * 0.5
local dx    = c * (1 - extra)               -- 绕中心 ⇒ p → extra*p + c*(1-extra)
G.push(); G.translate(dx, dy); G.scale(zoom, zoom); draw(); G.pop()
```

- fill=1 / extra=1.06 ⇒ `dx = 54 × (-0.06) = -3.24`（108 画布，中心仍在 54）。
- ⚠ `G.translate` **必须写在 `G.scale` 之前**，否则平移量也会被缩放。
- ⚠ 冷却罩只在 `fill > 1` 时按 `ICON_FILL` 几何改 size/pos；`extra` 是绕中心放大，不动罩。
- ⚠ 绝不能改 `btn.scale`（父 scale 连框一起放大）/ `btn.size`（布局+命中框）/ 图集 `size`
  （`anchor`、`icon_fill_zoom` 都按它算）—— 想调大小只有 `_draw_self` 这一条路。
- 只对单个法术生效 ⇒ 写成 `SpellTable.<id>.icon_zoom`，别动全局常量。

**⑧ ⭐⭐⭐ 插件帧名必须独占前缀 —— 本体图集是「按需装卸」的，会按名删帧**
事故（2026-10-20，用户实测）：插件火雨图集沿用 KR6 原始帧名 `rain_of_fire_*`，
与 Dove 本体 KRAB 里 **99 个同名帧**撞车（本体是 KR1 火雨，同源资产同名）。结果：

1. 玩家把**本体火雨**选进出战法术 ⇒ 本体加载自己的图集，同名帧**覆盖**插件那份；
2. 取消本体火雨 ⇒ 本体**按帧名卸载** ⇒ 插件启动时注册的帧被一并删掉；
3. 插件 `animation_db` 动画条目是持久的 ⇒ `build_link() missing frame`，
   陨石/爆炸/粒子/地面特效**永久隐形**（重启游戏才恢复）。

⇒ 规则：
- 插件图集的**帧名 + 动画名都要**独占前缀（帧 `kr6p_rof_hit_0001`、动画 `kr6p_rof_projectile_idle`）。
  **只改帧名不够** —— 同名动画条目同样会被本体覆盖，且报错日志里出现的就是动画名。
- 动画注册表的 key / `prefix` / 模板里 `sprite.prefix`、`particle_system.name`、
  `animated=false` 时的完整帧名，五处必须一起改（漏一处 = 静默隐形）。
- 移植前先查本体有没有同名帧，**只解析本体 bin**：
  ⚠ `_krab_check.py` 的 `_krab_index.json` = **本体 bin + 插件 lua 合并**的缓存
  ⇒ 拿它判「有没有同名」必然全中（全量假象）。正确做法：只 glob
  `KingdomRushDove/_assets/**/*.bin` 跑 `parse_krab`，再按前缀统计（本项目实测：
  `rain_of_fire_*`=99、`kr6p_rof_*`=0、其余插件前缀全=0 ⇒ 火雨是唯一冲突点）。
- `check_kr6_frames.py` 必须把**插件自带图集**的帧并入索引（`plugin_frame_names()`），
  否则独占前缀会整片 ⛔ 误报；反过来，只查本体索引时插件帧靠"与本体同名"侥幸判绿 = **假阳性**。

**⑨ ⭐⭐⭐ 更省事的路子：本体已有同源图集就直接借用（persistent_textures + 并进 game 组）**
火雨最终方案（2026-10-20，用户提案）：插件**不再自带** `go_power_rain_of_fire`
（省 317KB PNG + 16KB lua），直接用本体 KRAB。判据 + 三步：

1. **先核对是不是同一套素材**：本体 KRAB 里该前缀的帧数要与插件需求完全一致
   （火雨：projectile 8 / particle 10 / decal2 14 / hit 19 / hit_explosion 37 ⇒ 与 KR6 一字不差，同源）。
   不一致就别借（动画表 `to` 会越界）。
2. **锁常驻**：`image_db.persistent_textures[name] = true`。
   引擎 `unload_atlas` **第一行**就是 `if self.persistent_textures[name] then return end`
   ⇒ 本体按需装卸时永远删不掉它（这是"选本体火雨再取消导致插件特效消失"的根本解法）。
3. **借本体自己的加载链**：不要自己算 scale，HOOK `director.load_texture_groups`，
   在 `item_name == "game"` 时把图集名 `table.insert(groups, name)` —— **必须插在 `next()` 之前**
   （next 里就按 groups 加载完了）。由本体按 `texture_size` / `ref_height` / queue 规则算 scale
   （Dove：`game.ref_res = TEXTURE_SIZE_ALIAS.ipad = 768`，fullhd 图集 ⇒ **0.7111**；写 1 会大 1.39 倍）。
   `load_atlas_new` 读的是 `<path>/<name>.bin`（KRAB，`atlas_binary.unpack`），路径 =
   `KR_PATH_ASSETS_GAME_TARGET .. "/images/" .. texture_size`。

配套约束：
- **动画名仍要独占**（`kr6p_rof_*`）：防同名的 `animation_db` 条目被本体覆盖；
  只有**帧前缀**用本体的（`rain_of_fire_*`）。
- 模板里 `sprite.prefix` 用本体帧名，`sprite.name` / `particle_system.name` 用独占动画名 —— 两者别搞混。
- ⚠ 新增的 HOOK 会和其它 HOOK（如迪纳斯）**同文件同函数**，探针里凡按字符串位置判"追加是否在 next 之前"的，
  必须把查找起点限定到自己的段（否则命中的是别人的 `next`；`verify_kr6_denas_merge` 就这样误报过一次）。

- ⭐⭐⭐ **借了本体图集，模板 `sprite.scale` 必须同步去换算**（否则整体小 29%）。
  绘制链是 `sx = sx * f_sx * ss.ref_scale`（`all/render_utils.lua:130`）：
  | 图集来源 | 加载 ref_scale | 模板 scale 该写什么 |
  |---|---|---|
  | 插件自带（`ensure_atlas_loaded`） | **1** | 手乘 0.7111（如索罗 0.64 = 0.9×0.7111） |
  | 本体 KRAB | **0.7111** | **KR6 原值**（0.9 / 1 / 2） |
  ⚠ 同一法术里**混合两种来源**时（主模型借本体、小贴图仍用插件图集）要分成两个常量
  （索罗：`FX_SCALE = 1` 给本体帧，`EXTRA_SCALE = 0.7111` 给 `kr6p_sol_extra`），别合并。
  ⚠ 例外口径要问用户：火雨 2026-10-20 定版"**不做补偿**"（按本体尺寸，比旧版小 29% 是预期），
  这类"用户定版"必须写进代码注释，否则下次维护会当 bug 修掉。

**⑩ ⭐⭐ 连动画定义也可能不用注册 —— 先查本体 `game_animations.bin`**
Dove 本体 `kr1/spells/` 里已经集成了 KR6 的一批法术（aspect_of_sol / rain_of_fire / musketeers /
royal_edict / soaring_shop / teleportation_sigil / thunder_zapper / wintersongs_wrath / reinforcements_kr6），
对应动画也在 `kr1/data/game_animations.bin`。格式（`all/animation_db.lua:load`）：

```text
u32 anim_count
  × anim_count: u16 name_len + name, u16 prefix_len + prefix, u32 count
u16 × total_count    -- 每个动画的帧号序列（nums，通常是连续的）
```

判据：**动画名、prefix、count、帧号段全一致** ⇒ 插件**不要**再 `register_animations(...)`。
理由：注册等于用旧值覆盖同名条目（`animation_db` 后写覆盖），本体升级改了分段就会被"锁死"。
本项目索罗 13 条全部一致（`aspectofsol_lvl_3_idle` 1-50 / `walk` 51-92 / `attack_1` 93-136 …）
⇒ 直接删掉 `SOL_ANIMS`，只在模板里写 prefix。
⚠ 但插件**自研**的法术（迪纳斯等）本体没有，必须照旧注册。
配套检查：`check_kr6_sol_base_anims.py` 解析 bin 逐条断言（缺了就回退成自己注册）。

**⑪ 借用时"本体缺的那几帧"怎么处理**
索罗战吼 buff 的静态贴图 `kr6_sol_inspire_buff` 本体**没有**（本体走 exo 骨骼
`hero_gerald_inspire_courage_buff_decalDef`）⇒ 从旧图集裁出单帧，单独做**极小图集**
（`kr6p_sol_extra`，47×27 / 1.6KB），帧名改成独占前缀 `kr6p_sol_inspire_buff`。
⚠ 不要为了几帧把整个图集留下（索罗 3.9MB 里这帧只占 1.6KB）。

**⑫ ⭐⭐⭐ Steam 版会剥掉内购资源 —— 缺帧就去要手机版 APK**
龙息法杖（`user_item_rod_dragon_fire`）在 Steam 4.2.10 的 `go_towers` 里**只有 explosion 14 帧**，
图腾 41 / 火焰 10 / 火球 10 / 粒子 10 **全缺**（模板、动画表、存档字段 `backPack.currentRodDragonFire`
都在 ⇒ 不是没这功能，是美术被剥了）。
手机版 APK 解包（`assets/kr3-phone/images/iphonehd`）**5 组 85 帧齐全**。

- 手机版的图集 lua 是**纯文本** `return { ["name"]={size={..}} }`（Steam 版才是 LuaJIT 字节码）
  ⇒ **不用反编译**，直接正则解析（两种格式：多行 `name = {...}` 与单行 `["name"]={...}`）。
- 判据：Steam 图集 PNG 像素**已被索引 99.7% 覆盖** ⇒ 不是"索引被裁"，是资源真没打包。

**⑬ ⭐⭐⭐ 手机版 `iphonehd` 的缩放 = 768/960/0.95 = 0.8421（factor 是「除」）**
`all/director.lua` 的 `director:get_texture_scale(item_name, ref_res)`：

```lua
local scale = ref_res / TEXTURE_SIZE_ALIAS[self.params.texture_size]
local factors = TEXTURE_SIZE_FACTOR[self.params.texture_size]
if factors and factors[item_name] then
    scale = scale / factors[item_name]        -- ⚠ 除以 factor，不是乘
end
```

| 项 | KR3 手机版 | KR3 Steam fullhd |
|---|---|---|
| `TEXTURE_SIZE_ALIAS` | `iphonehd = 960` | `fullhd = 1080` |
| `TEXTURE_SIZE_FACTOR` | `{ game = 0.95 }` | 无 |
| 最终 load scale | `768/960/0.95` = **0.8421** | `768/1080` = **0.7111** |

**互证法**（换源必做）：拿两版都有的同一帧比"世界高度"——
手机版 `size 96×114 × 0.8421 = 96.0`，Steam `115×135 × 0.7111 = 96.0` ⇒ 精确相等，说明算对了。
⚠ 两版像素**不是等比重导出**（96/115 ≠ 114/135），所以不能靠像素比推 scale，只能各自算自版本再比世界尺寸。

**⑭ ⚠⚠ 两条会让探针写歪的引擎语义**
1. **`U.y_animation_play` 自己是阻塞协程**
   ```lua
   function U.y_animation_play(entity, name, flip_x, ts, times, idx)
       U.animation_start(...)
       local a = entity.render.sprites[idx or 1]
       times = a.loop and (times or 1) or 0
       while a.runs <= times do coroutine.yield() end    -- ← 播完才返回
   end
   ```
   ⇒ 写在它**之后**的代码要等动画播完才执行（原版"start 播完才显示火焰"就是这么来的，不是 bug）。
   探针里想走到后续逻辑，必须手动 `sprites[i].runs = 99` 推进。
2. **`U.find_foremost_enemy` 依赖 `spatial_index`**（`seek.id_arrays` 由 `seek.set_id_arrays` 注入）
   ⇒ 离线探针直调会崩 `all/seek.lua:439: attempt to index upvalue 'id_arrays' (a nil value)`。
   要测"发弹"路径必须 **mock 它**；同时 `simulation:queue_insert_entity` 需要补：
   `simulation.systems_on_queue_unconditional_count = 0`、`store.pending_inserts = {}`。

**⑮ 施法链路探针模板（带协程的道具/召唤物都适用）**
```lua
local store = { tick_ts = 0, tick_length = 1/30, entities = {},
                pending_inserts = {}, pending_removals = {} }
simulation.store = store
simulation.systems_on_queue_unconditional_count = 0
U.find_foremost_enemy = function() return fake_target, {fake_target}, fake_pred end   -- mock

local e = E:create_entity('<totem>')
e.pos.x, e.pos.y = 100, 200
e.fire_ts = 0 - e.fire_cooldown
e.render.sprites[1].runs = 0
local co = coroutine.create(Spells.<update>)

coroutine.resume(co, e, store)          -- 停在 start 动画
e.render.sprites[1].runs = 99           -- 手推
store.tick_ts = 0.5
coroutine.resume(co, e, store)          -- 走到喷火 → 断言 bullet.pos / from / to / target_id
-- 到期：runs 再推一次 + 多给一帧（y_wait_unconditional 首帧只登记起点）
```
断言点：火球起点 = 图腾位置 + `(0, 63)`、`to` = 预测点 + 敌人 `hit_offset`、`target_id` 绑定、
到期后 `sprites[2].hidden == true` + `e.pending_removal == true` + 协程 `dead`。

---

## 18. ⭐⭐⭐ 「点击调集时点身子选不中」= `ui.click_rect` 没跟着素材改

移植兵种（尤其可 `controable` 的援军）**默认继承本体民兵的 `r(-10, -2, 20, 25)`**
（20×25 世界单位，`all/templates.lua:928`），而移植素材画布 90~369 像素宽
⇒ 身体两侧、下半身、坐骑全在框外，点上去选不中（2026-10-19 用户实测两轮）。

**语义（必须记准）**
- `ui.click_rect` 是**世界单位**、原点在实体 `pos`、**左下 → 右上**（`all/components.lua:343` 注释）。
- 拾取 = `U.find_entity_at_pos`（`all/utils.lua:1603`）纯矩形包含；
  同点命中多个时按 `ui.z` 比，再按 `pos.y` 小的优先。
- 精灵绘制：画布按 anchor 对齐 pos、再乘 `sprite.scale`
  （`all/render_utils.lua:288`：`anchor.x*size - trim.x`、`(1-anchor.y)*size - trim.y`）
  ⇒ **世界坐标 = (画布坐标 − anchor × 画布尺寸) × scale**。

**做法**：写一个模板期工具，别硬编码手调

```lua
local CLICK_EXT_DOWN = 5    -- 下边再往下多扩（脚底/坐骑更好点）；试过 50 太大
local CLICK_SHRINK_TOP = 5  -- 上边往下收（不覆盖头顶空白，少抢别人点击）

local function fit_click_rect(tt, w, h, x0, y0, x1, y1, pad)
	local sp = tt.render.sprites[1]
	local sc = sp.scale.x or 1
	local ax, ay = sp.anchor.x or 0.5, sp.anchor.y or 0.5
	pad = pad or 6
	local rx0 = (x0 - ax * w) * sc - pad
	local ry0 = (y0 - ay * h) * sc - pad - CLICK_EXT_DOWN
	local rx1 = (x1 - ax * w) * sc + pad
	local ry1 = (y1 - ay * h) * sc + pad - CLICK_SHRINK_TOP
	tt.ui.click_rect = V.r(rx0, ry0, rx1 - rx0, ry1 - ry0)
end
```
⚠ 必须定义在 `register_templates` **之前**（文件级 local，向后定义会解析成 nil）。

**包围盒怎么取**
1. 读插件图集 lua，取该兵种 `idle + running/walk` 帧的 `size`（画布）与 `trim`（left, top, right, bottom）；
2. `x0 = min(trim.left)`、`x1 = w - min(trim.right)`、`y0 = min(trim.bottom)`、`y1 = h - min(trim.top)`
   （y 从**画布底**往上）；
3. ⚠ **别把 attack 帧算进去**：刀光/挥砍甩得很远（实测 kk 能到 85 宽 vs idle 43），
   框会撑到抢隔壁单位的点击。

**附带血案：anchor 抄错 = 单位陷进地里**
- KR3 `soldier_re_0` 是 `anchor_y = 10 / image_y`（image_y 54 世界单位 = 76 图集像素）⇒ **0.185**；
  当初照抄其它兵种写 0.5（画布中心对齐 pos），而该素材内容只占画布 y 9..76（下方 9px 空白）
  ⇒ 整个人**陷进地面约 17 世界单位**，用户\"点下面点不到\"正是点在陷下去的下半身。
- 判断锚点对不对的通用办法：`脚底_y = (trim.bottom − anchor.y × 画布高) × scale`，
  健康的兵种应该落在 **−3 ~ −5**（略低于落点）。

**探针要点**（本项目 `verify_kr6_click_rect.lua`）
- 数值：每个模板四边与手算值比对 + 比旧框大 + 有上限；
- 行为：`U.find_entity_at_pos({e}, pos.x+dx, pos.y+dy)` 真命中（四角/边中点必中、
  框外 3 单位必不中、**底边中点旧框会漏现在命中**）；
- 有效性：把 `CLICK_EXT_DOWN` 改 0 / 注释掉 `fit_click_rect` / anchor 改回 0.5 ⇒ 必须成片 FAIL。

---

## 19. ⭐⭐ 「原版技能图标不是这个」= 别拿头像顶替法术图标

搬法术时 `SpellTable.<id>.icon` 要的是**法术按钮图标**，不是单位头像/肖像
（2026-10-19 精灵援军就误用了 `..._face_a` 士兵头像，用户一眼看出不是原版）。

**KR Origins（KR3）的权威映射**（反编译 `all-desktop/game_gui.lua` 直接可读）：
```lua
Power1Button → "power_button_icons_0017"   -- 雷电
Power2Button → "power_button_icons_0018"   -- 援军（交叉双刀 + 橙底）
Power3Button → "power_button_icons_" .. ht.info.ultimate_icon   -- 英雄大招（每英雄不同）
-- 且 E:set_template("user_power_2", E:get_template("power_reinforcements_control"))
```
⇒ **援军就是 0018**。图标帧全在 `gui_common` 的 `power_button_icons_0001..0018`。
⚠ 拿不准时**先反编译 GUI 主文件**（`all-desktop/game_gui.lua`）搜 `power_button_icons`，
比在模板/关卡数据里翻半天快得多。

**抽图两个坑**
1. ⚠⚠ **`a_name` 必须按帧读**：KR3 `gui_common` 的 power 帧在 **`gui_common-2.png`**，
   固定用 `-1.png` 会裁出一堆碎片（每张都像"残缺的法术图标"）。
2. ⚠ **填充率要补齐**：KR3 图标画布 88×88 但内容只有 56×58（四周留白 16/15）。
   直接塞进 Dove 的 108 按钮会明显小一圈（就是之前"图标没占满"同款症状）
   ⇒ 撑到 **105×106 放进 108 画布**（对齐 KR6 原生图标 0.97 填充率）。
   56→105 约 1.9 倍，用 Upscayl `upscayl-standard-4x` 先 4x 再降采样，边缘更实。

**探针**：断言 `icon` 名、该帧在图集里、`size == {108,108}`，并确认头像帧仍保留给信息条。
