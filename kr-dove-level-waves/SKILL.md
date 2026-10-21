---
name: kr-dove-level-waves
description: 王国保卫战 Dove 版自建关卡的出怪波次、路径机制与关卡脚本挂点：波文件帧单位语义（interval/delay/max=0 空档）、编辑器 _config.lua 与编译态 _waves_campaign.lua 的字段映射、钉死节奏/单人双人阵型/同组混编穿插/子波起始延迟等距摊开（DELAY_SPREAD，消除"开局多路齐爆、之后一路独走"）、paths.lua 的 connections 汇入规则（28px 阈值与回退坑）、出口/防御点/扣命链路、"第 N 波起敌人加血/加速"这类波次级数值强化的 insert 钩子写法、**自己画的整张地图大图当关卡背景（图集描述/plugin_required_textures 四件套、1920x1080 口径、16:9 与 4:3 的可见区域裁切差异）**、出怪审查清单。设计自建关卡出怪、改出怪节奏与阵型、接入自定义地图背景图、排查"怪不走/横穿地图/不扣命/数值强化不生效/背景空白"时使用。
agent_created: true
---

# KR Dove 版自建关卡：出怪与路径机制

适用：给 `mods/local/<plugin>` 这类自建关卡设计出怪、审查已有波次、排查路径/出口相关的运行时异常。

## 一、插件关卡的文件布局

```
<plugin>/
  config.lua                                  entry=<plugin>, category="level", priority
  <plugin>.lua                                主入口，返回 hook（常只需 init/unload 空实现）
  assets/images/<名字>.lua                    自定义图集（单帧页，a_name=实际 png 文件名）
  data/levels/<plugin>_data.lua               实体列表 + nav_mesh + required_textures
  data/levels/<plugin>_paths.lua              active / connections / curves / paths
  data/levels/<plugin>_grid.lua               网格
  data/levels/<plugin>_metadata.lua           thumbnail / category
  data/levels/<plugin>.lua                    ★自定义 level 模块（会覆盖原版关卡主循环！）
  data/waves/<plugin>_waves_campaign.lua      ★游戏真正读的编译态波文件
  data/waveconfigs/<plugin>_waves_campaign_config.lua   编辑器源文件（运行时不读）
```

- 关卡数据必须包含 **`decal_defend_point`（带 `editor.exit_id`）**，否则自定义 level 里调 `LU.insert_hero` 会在 `all/level_utils.lua:470` 崩 `attempt to index field 'exits' (a nil value)`。兜底修法：给 `store.level.custom_spawn_pos` 赋值，`insert_hero` 会优先用它。
- 自定义 `<plugin>.lua` 的 `level:update` 若重写了主循环（`while not store.waves_finished or LU.has_alive_enemies(store) do coroutine.yield() end`），要自己保证开局资源注册齐全，不能只照抄这一句。
- `level:update` 被引擎当协程跑（`all/systems/level.lua:284-304`：`coroutine.create(store.level.update)` 后 `resume(co, store.level, store)`），所以签名是 `function level:update(store)`，且**每次 resume 只推进一次 yield**。

### 关卡脚本的常用挂点：`U.insert_insert_hook`（做"波次级"数值强化）

要给"第 N 波起敌人 +10% 血、+5% 移速"这类**按波号**的强化，不要改模板，挂 insert 钩子逐只乘。

**⚠ 必须用引擎官方 API `U.insert_insert_hook(store, E.last_id, fn)`，不要手写 `table.insert(store.last_hooks.on_insert, fn)`。**
全仓一致惯例（8 个自建关卡 + 原版自己都这么写）：
`kr1/data/levels/level116.lua:26`（原版）、`mods/local/BleakDune/.../BleakDune.lua:19`、
`DemonRealm:137`、`Twilight_elf_final:246`、`ilor_Cloister:34`、`ilor_Plain:29`、`ilor_final:171`、
`ilor_outpost:22`、`mage_forest:43`（`zhaozedixue` 是经 `next-wave-ready` 信号挂的变体）。

标准骨架（照抄即可，`BleakDune` 与"后三波强化"是同一个 shape）：

```lua
local function buff_enemy(this, store)
	if not this.enemy then return end
	if (store.wave_group_number or 0) < BUFF_FROM_WAVE then return end
	if this.health.tl_buffed then return end                 -- 幂等（见规则 5）
	this.health.tl_buffed = true

	this.health.hp_max = math.floor(this.health.hp_max * HP_MUL)   -- 用 math.floor，与本体一致
	this.health.hp = this.health.hp_max                            -- 按新上限回满

	if this.motion and this.motion.max_speed > 0 then               -- 0 = 固定不动单位，别碰
		U.speed_mul_self(this, SPEED_MUL)                          -- ⚠ 必须走这个
	end
end

function level:update(store)
	-- 钩子签名就是 (实体, store)，与 last_hook.lua:50 的 hook(e, d) 一致
	U.insert_insert_hook(store, E.last_id, buff_enemy)
	E.last_id = E.last_id + 1            -- ⚠ 必须自增占位，见规则 3
	log.info(...)                        -- 可选；本体 level106 也这么打日志

	if store.selected_hero then LU.insert_hero(store) end
	while not store.waves_finished or LU.has_alive_enemies(store) do coroutine.yield() end
end
```

五条硬规则（都踩过）：

1. **波号只能读 `store.wave_group_number`**（`wave_spawn.lua:161`，进某组前赋值、组内 spawner 全跑完才推进 → insert 时读到的一定是"它是第几波的"）。
   `e.enemy.wave_group_idx` **只在 debug 模式**被写（`game.lua:696`），常规出怪器不写（`wave_spawn.lua:30-70` 只设 `nav_path`/`spawn_data`）。
2. **挂在 `level:update` 而不是 `level:init`**。两个原因：
   (a) `store.last_hooks` 由 `last_hook:init` 建（`last_hook.lua:5-12`），而 systems 顺序里 level 排第 1、last_hook 排倒数第 3（`game.lua:137`）→ `level:init` 时它还是 nil，`U.insert_insert_hook` 会直接索引 nil 报错；
   (b) `last_hook:on_insert_unconditional` 在**同一帧**所有系统的 `on_insert_unconditional` 之后才跑钩子（`last_hook.lua:45-51`）→ 此时 `enemy.lua:36-51` 已把 `hp_max` 按难度打完补丁、并把 `hp` 填满 → 乘完就是终值，不会被覆盖。
   **写在 `while` 循环之前就够了**：`level:update` 是协程体（`level.lua:284-304`），只跑到第一个 `yield` 就停 → 天然只挂一次，不需要 `hooked` flag / `ensure_hook` 那套。
3. **`E.last_id` 挂完必须 `+1`**：`U.insert_insert_hook` 把钩子存在 `last_hooks.on_insert[id]`（`utils.lua:2806-2812`）里**按 id 作 key**，不自增就会被后一个同 id 的钩子**静默顶掉**（`E.last_id` 定义在 `entity_db.lua:18`，每次 `E:Load()` 重置为 1）。另有 `U.remove_insert_hook(store, id)`。
   ⚠ 用 `key` 而非数组还有个好处：同 id 重复挂是幂等的；用 `table.insert`（数组）重复挂会**每帧加一条**，只能靠自己的 flag 兜。
4. **改速度只能走 `U.speed_mul_self(e, f)`**（`utils.lua:2442`：乘 `max_speed` 再重算 `real_speed`）。
   只改 `max_speed` 会被 `last_hook.lua:45-46` 的 `real_speed = max_speed` **抢先定死**（那行在钩子之前执行），实际移速不变。
   `real_max_speed`（`:2398`）读 `motion.factor/buff`，由 `components.lua:74-75` 初始化为 1/0，insert 时一定存在。
   ⚠ `max_speed == 0` 的固定不动单位要**跳过**：乘完仍是 0，但 `real_speed` 会被 `clamp(1, 10000, …)` 的下限**抬成 1** → 静止单位开始蠕动。
5. **加一句幂等守卫**（`this.health.<自定义>` 标记）。通行写法一般不加，但 `enemy.lua:40` 的 `if not entity.health.patched` 说明引擎**预期实体可能重复走 insert**，
   而且变形/poly 会把这个 `patched` 继承给新实体（`all/scripts.lua:7271`、`boss_scripts.lua:9985`、`hero_scripts.lua:24285`、`game_scripts.lua:1395`）。

⚠ **乘实体，别乘模板**：`DI:patch_templates()`（`difficulty.lua:14`）在 `store.level:init` **之后**才跑（`level.lua:77-81`），
它用 `PT()`（`:15-27`）把模板里**数组格式**的 `hp_max`/`max_speed` 按难度解析成标量。
在 `level:init` 里乘模板会踩到数组（`{5,12,22,36}` 之类），所以一律 insert 时乘实体终值。
（因此 insert 时 `hp_max` 必是 number，不必再加 `type()` 守卫；`math.floor` 取整与本体 `difficulty.lua:64` 口径一致。）

**两种效果实现风格**，按需选：
- **直接改字段**（`BleakDune`、原版 `level116`、Tropical_Loop）：血量/赏金这类"一次性静态调整"，改完不需要维护。
- **挂 modifier 实体**（`mage_forest`、`DemonRealm`、`ilor_outpost`、`zhaozedixue`）：需要受伤倍率、护盾、按时间衰减或需要被移除的场景 ——
  注册一个 modifier 模板，`E:create_entity` 出来设 `m.modifier.target_id = this.id`，再 `simulation:queue_insert_entity(m)`，效果写在该 modifier 的 `main_script.insert` 里。

功能级自测（比语法校验更值）：`.workbuddy/test_late_wave_buff.py` —— 用游戏自带 `lua51.dll` 起真状态，
`luaL_loadbuffer` 把关卡脚本编译成函数塞进全局（绕开中文路径的 `loadfile` 编码问题），
桩掉 `level_utils`/`entity_db`/`utils`/`lib.klua.log`（`entity_db` 要桩 `last_id`，`utils` 要桩 `insert_insert_hook`），
协程跑一次 `level:update` 装上钩子，再喂假敌人断言（钩子 key 落在 `E.last_id`、`E.last_id` 已自增、
波号边界 / 取整 / 幂等 / 静止怪 / 非敌人实体不动）。
⚠ `lua_setglobal` 在 Lua 5.1 是宏、**未导出**，要用 `lua_setfield(L, -10002, name)`。

## 二、波文件两套形态（**最容易搞混的地方**）

| | 编译态 `_waves_campaign.lua` | 编辑器源 `_config.lua` |
|---|---|---|
| 谁读 | 游戏 `all/wave_db.lua:836` | 仅 `all/game_editor.lua` 读写 |
| `interval` 单位 | **帧** | **秒** |
| 出怪表达 | `waves[].spawns[]{creep, max, interval, path, fixed_sub_path}` | `waves[].enemies[]{...}, formation, rest, weight` |
| 额外字段 | — | `total_gold`（估算值，游戏不读） |

**在编辑器改完必须点「生成出怪」，否则编译态不更新。** `total_gold` 只是估算：实算 = Σ(该单位数量 × `enemy.gold`)，与显示值可能差几只的赏金。

### 编译态字段语义（`all/systems/wave_spawn.lua`）

- `fts(v) = v / FPS`，`FPS = 30`（`all/constants.lua:9`）→ 波文件里的时间量全是帧。**秒 × 30 = 帧**。
- `wave.delay`：该子波相对**本组开始**的延迟（各子波协程同帧创建，`wave_start_ts` 同帧取，所以是相对组起点）。各子波是**并行**跑的，不是排队。
- `spawn.max`：该条目出兵数；`spawn.interval`：条目的出兵间隔（帧）。
  - 循环是 `for j = 1, s.max do y_wait(interval); create end`（`wave_spawn.lua:41-42`）→ **第一只之前也要先等一个 interval**，所以 N 只的条目实际耗时 ≈ **N × interval**（不是 (N−1) × interval）。调"每只间隔"就是改这个字段。
- `spawn.interval_next`（`wave_spawn.lua:76-92`）：**条目之间**（`i < #spawns`）的额外等待帧。Hard 难度按 `group_id`（>6 / >9 / >12）把它压缩到 75% / 50% / 25%，并同步回拨 `last_wave_ts`，因此高波次会明显提速。
- `group.interval` 的**起算点**：`store.last_wave_ts` 是在**该组所有子波协程全部结束之后**才置位的（`wave_spawn.lua:219-224`），下一组再等 `group.interval`（`:154`）。即"组间距"从**上一组出完**那刻开始算，不是从上一组开始算。GUI 倒计时与提前召唤奖励也用这个差值（`:165-177`）。
- **`max = 0` + `interval = N` 是纯空档**（`wave_spawn.lua:66-68` 额外等 N 帧）——编辑器「波长/秒」就是被摊成若干个这种空档，**它们的 interval 之和 = 编辑器填的波长秒数 × 30**。
- `fixed_sub_path == 1` → `e.nav_path.spi = spawn.path`（指定子路径）；`0` → `random(#path)` 随机。
- `wave.path_index` = 路径组号；`spawn.path` = 子路径号。
- 编辑器「留白 rest」**不写进编译文件**，它只参与算 `group.interval`：`group.interval ≈ 子波时长 + rest`。
- 无害的编辑器产物：`some_flying`（引擎内部自己算）、`max_same`/`creep_aux`（未启用时为 0/缺省）。

### 编辑器面板字段 ↔ 编译态映射（`all/game_editor_wave_config.lua`）

编辑器「出怪配置」面板字段与编译态一一对应，**编辑器填秒、编译态存帧**：

| 面板字段 | 变量 | 编译态 | 作用 |
|---|---|---|---|
| 持续时间/秒(interval) | `group.interval` | `groups[].interval = ×30` 帧 | 本波总时长；**同时**是"本组出完后"到下一组的等待 |
| 本波金币量(gold) | `group.total_gold` | 不写（仅编辑器反推数量） | 本波总金币 → 数量 |
| 子波N 延迟/秒(delay) | `wave.delay` | `waves[].delay = ×30` 帧 | 相对**本波起点**的偏移；各子波**并行** |
| 子波N 波长/秒(interval) | 派生、不落盘 | 摊怪窗口（帧 = ×30） | 子波内全部敌人摊在这段时间 → **就是"出怪间隔"旋钮** |
| 子波N 留白/秒(rest) | `wave.rest` | 不写（只参与算波长） | 子波末尾留白，让本子波提前出完 |
| 子波N 权重(weight) | `wave.weight` | 不写（只参与金币拆分） | total_gold 在各子波间怎么分 → **影响数量，不影响间隔** |
| 子波N 路径(path_index) | `wave.path_index` | `waves[].path_index` | 走哪个路径组 |
| 阵型(formation) | `wave.formation` | 展开成 `max=1` 条目 + `max=0` 空档 | 随机摊开 vs 按批次摊开（黄色高亮 = 开） |
| 生命值(lives) / 初始金币(cash) | store 级 | — | 与出怪节奏无关 |

**三字段硬约束（面板自动联动）**：`延迟 + 波长 + 留白 = 持续时间`（`:334` 注释 + `:292-351` 的 on_change 互相回填）。改"持续时间"会重算每个子波波长；改"波长"/"留白"互相回填。

**波长怎么变成间隔**：`generate_wave` 把该子波敌人拆成若干 `max=1..8` 批次，再把波长(帧)随机分给各批次，最后 `table.random_order` 打乱顺序（`interface.lua:393-438`）→ **同一波长下，数量越多 → 每批间隔越短**。formation 走另一条路：每只单独一条 `max=1`，按 1/2/3 路组成"阵型小组"，小组间插 `max=0` 空档，空档之和 = 波长（`:282-303`）。

**"持续时间"的双重身份（容易踩）**：`group.interval` 从**本组所有子波出完**那刻起算（`wave_spawn.lua:219-224` → `:154`），不是从本组开始算。所以
- 周期 ≈ 2 × 持续时间 − min(各子波 rest)；
- **留白调大 → 本子波更早出完 → 下一组反而更早开始**；
- 缩短"持续时间"不仅让本波更密，也会让下一波提前。

**三个保存按钮的区别（`game_editor_wave_config.lua:568-599`）**：
- 「生成出怪」`_generate_waves`：只重算到内存 `editor.wave_data`，**不写盘**。
- 「保存配置」`_save_config`：只更新 `wave_config`，`wave_data` 仍是上次生成的内存副本 → **可能存出一份 config 与 waves 不匹配的文件**。
- 「保存出怪」`_save_waves`：先重算 `wave_data` 再连配置一起落盘 ✅ 改完间隔用这个最稳。
- 落盘位置：编辑器走 `love.filesystem` → `plugins/<entry>/data/{waveconfigs,waves}/...`，即 **AppData**，不是工作区副本（`game_editor.lua:976-998`）→ 编辑器存完记得把 AppData 反向同步回工作区，否则下次从工作区覆盖会把编辑器改动冲掉。

### 钉死出怪节奏（确定间隔带）—— 手写编译态

想要「每只/每批间隔严格落在 X~Y 秒」这种**确定节奏**，编辑器的生成器给不了（它把波长随机摊给各批次）。做法是**手写编译态**：

- 一批 = 同时出 1~3 只（占多条子路径），写成一串 `max=1, interval=0, interval_next=0` 条目；
- 批与批之间插一条 `max=0, interval=G` 的空档，**G 就是"批间隔"（帧）**；
- 子波的摊怪窗口 = ΣG，即编辑器里的「波长」；
- 起始延迟：**两种布局二选一**（用 `DELAY_SPREAD` 切换）——
  `0` = 串行重叠（后一个子波在前一个出到 ~60% 即 `OVERLAP` 时接上）；
  `1` = **等距摊开**（推荐，见下节「子波起始延迟」）把各子波的出怪期均匀铺满本波跨度。
- `持续时间 = 本波跨度 span + BREATHER`（帧），`留白 = 持续时间 − 延迟 − 波长`。
  ⚠ span 取的是**串行布局**下的 `max(延迟 + 波长)`，与选哪种布局无关 ——
  所以调摊开程度**不会**动波间隔与全关时长。
  **BREATHER 就是"出完后到下一波的喘息"**（因为 `group.interval` 从本组出完那刻起算）；
- 全关时长 ≈ Σ(出怪跨度 + 持续时间) = `2·Σ出怪跨度 + 波数 × BREATHER`；
- **G 取 3 的整数倍** → 秒数恒为 0.1 的整数倍，配置态好看、无浮点毛刺；
- 批数决定波的长短：`批数 ≈ ceil(数量 / 每批只数)`，每批 2~3 只时波最短。想拉长波就减小每批只数（但阵型小组 ≤ 3 路）；
- 动手前**核对每个路径组有几条子路径**（阵型最多占 3 路），见 `paths.lua`。

#### 阵型可手写（单人/双人、同组内混编穿插）

批次的**只数**就是阵型，别用"平均每批几只"去自动切，要能逐子波指定：

- **批次只数 = 该批同时占用的子路径条数**。数量除不尽时最后一批判余数（≥1）。
- 用 `SQUAD_PATTERN` 元组循环控节奏：`(2,1)` = 双人/单人交替（均 1.5 只/批）、`(2,2,1)` = 双人为主、
  `(1,1,1,2)` = 单人为主。子波级可用 `"pattern": (1,)` 覆盖成全单人。
- **⚠ 只数变小的代价**：批数变多 → 在间隔不变的前提下**波长和整关时长都会变长**
  （`批数 ≈ ceil(数量/每批只数)`，每多一批多一个 G）。把大怪间隔从 2~3.5s 拉到 5~7s 尤其明显：
  单是这一条就能把全关从 14 分钟推到 17 分钟。改完记得看脚本打印的"全关预计时长"，
  太长了就减 `BREATHER` 或放大 `SQUAD_PATTERN` 的均值。

**大怪档的独立规则**（和全局 pattern / 小怪带解耦，`BIG_ENEMIES` 那一档）：

- `BIG_MAX_SQUAD`：中大型怪每批只数上限（`1` = **永远单只推进、绝不并排**，与全局 `SQUAD_PATTERN` 无关）。
  ⚠ 实现要点是**先把 pattern 夹一遍再切批次**（`tuple(min(p, lim) for p in pattern)`）；
  夹在切之后会破坏总数量。
- `BIG_BAND` / `BIG_BAND_LATE` + `BIG_BAND_SWITCH_WAVE`：中大型怪批间隔可分段
  （例：前 13 波 5~7s 拉开压迫感，第 14 波起回到 2~3.5s 做收尾高潮）。
  ⚠ 分档判定要写成 `小怪带 if e not in BIG_ENEMIES else (后段 if wave >= 切换波 else 前段)` ——
  Python 的 `A if x else B if y else C` 会解析成 `A if x else (B if y else C)`，
  写成 `big_late if wave>=sw else big if is_big else small` 会把**中小怪也套上大怪带**。
- 导出 JSON 时把 `gap_bands`（每个间隔**实际用**的带）一起写进去，校验器直接按它判越界，
  不必在校验器里重算分档逻辑（重算就又多一处可能漂移的硬编码）。

**混编穿插（不同兵种在同一子波里轮流出）**：

- 一个子波写多个兵种，批次按**等距落点**合并（`merge_evenly`）：各兵种算自己每个批次的落点
  `pos = (k + 0.5) * 总批数 / 自己的批数`，再按 `pos` 排序。
  ⚠ 别用简单 round-robin：批次少的兵种会**全挤在开头**（10 只大怪 + 2 批小怪 → 小怪都在前两位）。
  等距落点才让"中大型怪单只推进 + 小怪填缝"真正铺开。
- **⚠ 硬约束：一个子波只归属一个路径组**。`wave_spawn.lua:39` 取 `P.paths[wave.path_index]`，
  `:55` 每条 spawn 的 `e.nav_path.spi = s.path` 只能是**该组内**的第 1..N 条子路径
  （`fixed_sub_path == 1` 时用 `s.path`，否则 `random(#path)`）。
  **所以跨路径组的兵种塞不进同一个子波** —— 想穿插，两个兵种必须同组。
- **让中大型怪和小怪同路穿插的最省事做法：往该路"新增"小怪**，而不是把别路的小怪搬过来 ——
  新增的小怪本来就不存在，走哪条路都不算"改路线"，所以**原有任何兵种的路径都没动**。
  设计表里把新增的记成 `(敌人, 数量, "add")`，脚本按 `MAX_ADD_SMALL_PER_WAVE` /
  `MAX_ADD_SMALL_TOTAL` 断言预算（Tropical_Loop 现为每波 ≤10、全关 ≤40，实际用 32）。
  报告里给这些兵种打 `新` 标记，方便区分"原有数量"和"新增陪衬"。
- 每个兵种各自保留自己的**批间隔带**（中大型怪走 BIG_CYCLE、小怪走 SMALL_CYCLE）；
  混编时按"刚出完那批的兵种"取带，两档各自独立计数 → 结果确定、可复现。
- **⚠ 混编子波在编辑器里无法还原**：`generate_wave` 调 `distribute_total_amount_to_groups_randomly`
  时**没传 weights**，多兵种的金币是**随机**拆的 → 点「生成出怪」得到的数量配比是随机的。
  混编波只能以脚本为真源。

**⚠ 中大型怪单只 + 长间隔会把波拉得极长**：波长 ≈ `(只数-1) × 间隔`。
12 只兽人勇士单只 + 5~7s → 一段就 60s+，加 20s 喘息单波 90s。Tropical_Loop 实测：
从 14 分钟一路推到 **22 分钟**。动机上是对的（"一只一只来"），但要知道代价。

#### 子波起始延迟：等距摊开（`DELAY_SPREAD`）

**串行重叠的副作用**：后一个子波在前一个出到 60% 时接上 → 所有"窗户小"的子波都挤在
**波的开头同时爆发**，之后长时间只剩最长的那一个子波。Tropical_Loop W8 实测：

| 子波（路径） | 串行重叠 | 等距摊开 |
|---|---|---|
| sub1 兽人勇士×12（路1） | delay 0 → 出怪期 0~4.7s，**留白 87.7s** | delay 33.8s，留白 53.9s |
| sub2 萨满×4（路2） | delay 2.8 → 2.8~6.0s，**留白 86.4s** | delay 58.7s，留白 30.5s |
| sub3 混编 15 只（路4，波长 67.7s） | delay 4.7 | delay 0 |

→ 开局 6 秒三路齐爆，随后 66 秒只有一条路：玩家开局瞬间被三路夹击、之后长时间无事。

**做法**：把各子波的**出怪期**在 `[0, span]` 上等距铺开 —— 按 `window` 从大到小领位，
第 k 个子波的**出怪期中点**落在第 k 段的中心 `(k + 0.5) × span / n`，再夹进
`[0, span − window]`，最后 3 帧对齐。这和批次级的 `merge_evenly` 是**同一个思想**
（等距落点），只是作用在子波这一层。

- ⚠ **span 必须由串行布局算出并保持不变**，不能换成摊开后实际的 `max(delay+window)`：
  否则全关时长跟着缩水 —— 那是"压缩时长"，不是"摊开"。
- ⚠ 最长 window 的子波会被排到 `delay = 0`，这保证波一开始就有怪（否则开头会静默几秒）；
  代价是末尾可能空出一小段，并入喘息即可。
- ⚠ **别用"平均同时活跃子波数"衡量效果**：Σ波长守恒，该值恒为常数、零信息量。
  要看**「开局 / 收尾 N 秒内的活跃子波数」**（Tropical_Loop：开局 6 秒 27→20，收尾 6 秒 24→32）。
- ⚠ 报告/统计脚本里算持续时间要读**真源里的 `dur`**，别再用 `max(delay+window)` 反推 ——
  摊开后它不再等于 span，会把全关时长算少（本项目踩过：报告显示 22.2 分钟还算对，
  但换个数据就会漂）。

⚠️ **这套手写编译态不能被编辑器再生**：一按「生成出怪」/「保存出怪」，波长会被重新随机摊开、节奏当场丢失。
所以此时**设计表 + 脚本才是 source of truth**，编辑器只用来肉眼核对配置态。

Tropical_Loop 的现成工具（`<ROOT>/.workbuddy/`）：
- `gen_tropical_loop_waves.py` — 设计表 → 编译态 + 配置态。
  - 顶部可调：`SQUAD_PATTERN`（小怪批次只数循环）、`BIG_MAX_SQUAD`（中大型怪每批上限，1=永不并排）、
    `SMALL_BAND`/`SMALL_CYCLE`、`BIG_BAND`/`BIG_CYCLE`（前段中大型怪带）、
    `BIG_BAND_LATE`/`BIG_CYCLE_LATE`/`BIG_BAND_SWITCH_WAVE`（后段）、
    `MAX_ADD_SMALL_PER_WAVE`/`MAX_ADD_SMALL_TOTAL`（新增陪衬小怪预算）、
    `OVERLAP`、`BREATHER`、`BIG_ENEMIES`、`LANES_PER_GROUP`。
  - `WAVES` 设计表每个子波写成 `{"path": 路径组, "squads": [(敌人, 数量), ...]}`；
    squads 多个兵种 = 同子波穿插；`(敌人, 数量, "add")` = 新增陪衬小怪（计入预算）；
    可选 `"pattern"` / `"lanes"` 覆盖。改阵型只改这里。
  - 改间隔带只需改对应的 `*_BAND`（帧）+ 同步 `*_CYCLE` 里的值落在带内；cycle 的均值 ≈ 该档平均间隔。
  - 跑完打印全表 + 新增小怪预算 + "全关预计时长"，并导出 `.workbuddy/tropical_loop_pacing_plan.json`
    （**元数据 band(+late/switch)/breather/squad_pattern/big_max_squad/add 预算/added_small_total/
    lanes_per_group/big_enemies/gold/name_cn + 逐子波 rows（含 batches/gaps/gap_bands/added）**）。
- `verify_paced_waves.py` — **以那个 JSON 为真源**逐项对账编译态与配置态：
  批次只数 / 占用子路径 / 各兵种数量 / 延迟 / 路径组 / 批间隔带 / 波长自洽 / total_gold / weight / rest。
  （旧版是"从配置反推数量"，混编子波下不成立，已弃用。）
- `make_pacing_report.py` — 读同一个 JSON 渲染 HTML 阵型表：**批序用彩色 chip 显示每个兵种的只数与占用的子路径**，
  混编行高亮；卡片（批型 / 混编数 / 间隔带 / 喘息 / 全关时长）全是变量。

标准闭环（改节奏/阵型时照做）：`gen_tropical_loop_waves.py` → `verify_paced_waves.py` → `make_pacing_report.py`
→ `lua_syntax_check.py <两个波文件>` → 复制到 AppData 并 `diff` 确认一致。



`generate_group(cfg)` → 每子波 `interval = (group.interval - delay - rest) * 30` 帧；
`total_gold` 按各子波 `weight` 拆给子波（`distribute_total_amount_to_groups_randomly(total, n, 0, weights)`）。

`generate_wave(cfg)` 里 **数量是由金币反推的**：
1. `golds = distribute_total_amount_to_groups_randomly(gold, #enemies)` —— 注意**没传 weights**，所以一子波多兵种时是随机拆分；
2. `counts[i] = ceil(golds[i] / template.enemy.gold)`。

**所以想让「配置态」与「手写编译态」数量一致，必须遵守两条**：

- 每个子波只放 **1 个兵种**（否则金币拆分随机 → 数量随机）；
- 显式写 `weight`，且 **weight = 该子波期望金币 = Σ(数量 × 单价)**，并令 `total_gold = Σ weight`。
  这样 `floor(total × w_i / Σw) = w_i` 无损，`count = ceil(count×单价/单价) = count`，精确复现。

`formation = true` 时走 `generate_formation_wave`：每只单位单独一条 `max=1, interval=0, fixed_sub_path=1` 条目，
路径按阵型小组取 1/2/3（1 只走 1，2 只走 2/3，3 只走 1/2/3）；小组之间插一条 `max=0` 的空档，
空档之和 = 子波帧长，但空档值本身是随机拆的（`roll_size` 也随机）→ **重生成只保证数量，节奏与路径会变**。

编译态没写 `weight`/`gold`/`formation`（那是配置态字段），只会出现 `delay / path_index / some_flying / spawns`。
`some_flying` 只被 GUI 用来在波次旗上显示飞行提示（`all-desktop/game_gui.lua:1266`）。

### 各单位基础数值在

`tt.enemy.gold`（赏金）、`tt.enemy.lives_cost`（扣命，默认 **1**，`all/components.lua:445`）、`tt.health.hp_max`、`tt.health.armor`（物理）/`magic_armor`、`tt.motion.max_speed = x * FPS`、`tt.melee.attacks[1].damage_min/max`。**远程伤害不在 enemy 模板里**，在对应 bullet 模板的 `tt.bullet.damage_min/max`。

难度缩放（`all/difficulty.lua` + `kr1/game_settings.lua`）：`hp_max` ×{1.3, 1.65, 1.65, 2}（Easy/Normal/Hard/Impossible）；`hp_max_evolved` 不缩放；速度 ×{1.2,1.2,1.25,1.25}；护甲 +{0,0,0.1,0.1}。

## 三、路径与 connections（**隐藏最深的一个坑**）

`<plugin>_paths.lua` 顶层：`active`、`connections`、`curves`、`paths`。`paths` 是 `[路径组][子路径][节点]`。

`connections[from] = to` 表示：**单位走完 `from` 组的子路径后，接着走 `to` 组**（`path_db:nodes_to_goal`/`next_entity_node`）。同一 `to` 有多条来源时反向索引会被覆盖，尽量保持一对一。

### 汇入点是自动算的，靠距离阈值，超限会回退到路径**起点**

`path_db:collect_connect_info`（`all/path_db.lua:55`）：对 `from` 组每条子路径取**最后一个节点**，在 `to` 组的**同名子路径**里找最近节点；若距离 `> PATH_POINTS_DISTANCE * 4`（`all/constants.lua:5` = 7，即 **28px**）就回退成 `ni = 1` —— 直接跳到 `to` 组的**起点**，表现为怪瞬间跑到地图另一头再横穿回来。

所以**改路径后一定要核对 connections**：把每组子路径的终点和候选目标组同名子路径的节点做最近距离，必须 < 28px。可直接跑：

```
python <skill>/scripts/check_path_connections.py <..._paths.lua>
```

（脚本会打印每组每条子路径的实际最近距离与「命中 / 超限回退」判定，并顺带做括号平衡校验。）

### 路径宽度（`curves[].widths`）：编辑器显示是一回事，游戏里生效是另一回事

`curves[i].widths[k]` 是第 k 个**节点**（user_point）处的宽度，编辑器 GUI 里字段名就叫 `node_width`
（`all/game_editor_gui.lua:2139`），默认 **40**（`all/game_editor.lua:65 DEFAULT_PATH_WIDTH = 40`）。
各点宽度不要求一致（热带回环就是 30/25/27/40 混着写）。`#widths = #segments + 1 = #user_points`。

⚠ **运行时完全不读 `widths`**。`path_db:load` 只 merge 编译态的 `paths`。宽度是在**编辑器保存那一刻**
由 `P:generate_paths()`（`all/path_db.lua:818-866`）从 curves 烘焙成几何的：

```
paths[pi] = { 中心线, 中心线 + (w/2)·perp, 中心线 - (w/2)·perp }
```

而 `all/systems/wave_spawn.lua:55`：

```lua
e.nav_path.spi = s.fixed_sub_path == 1 and s.path or random(#path)
```

—— 敌人是在这几条子路径里**随机挑一条**走的。所以 **路径宽度 = 兵线间距**：
w=40 时三条兵线落在 −20 / 0 / +20，w=30 时落在 −15 / 0 / +15。
**只改 `widths` 不改 `paths`，游戏里一点变化都没有**（要等下次在编辑器里保存才会重算）。

要改宽度用：

```
python <skill>/scripts/set_path_node_width.py <..._paths.lua> <新宽度> [--apply]
```

做法是「**中心线一个字节不动的等比缩放**」：只把 `paths[pi][2..n]` 相对 `[1]` 的偏移乘 `新/旧`，
于是**点数、点索引、node 编号全部保持原样** —— 这是硬要求，node 编号被波次配置和 `connections` 引用。
脚本只在「该关各点宽度完全一致」时才动手；宽度是渐变的（如热带回环）就拒绝，必须回编辑器改完重存。
改前自动备份到 `.workbuddy/backups/`；不带 `--apply` 只干跑打印报告。

**另一个独立旋钮**：`P:path_width(pi)`（`all/path_db.lua:195`，默认 **42**）。
`path_widths[pi]` 只能靠 `P:set_path_width(pi, v)` 设置（原版唯一用例 `kr1/data/levels/level36.lua:70-71`），
**把路径画窄/画宽不会自动改它**。它只管 `valid_node_nearby`，即「离路径多远还算在路径上」：
集结点合法性（`all/utils.lua:3150`、`all/scripts.lua:8081`）、技能/传送落点，
以及下一节那个 `decal_defend_point` 吸附阈值 `path_width * 0.5`（42 → 21px）。

## 四、出口、防御点与扣命

1. `scripts.decal_defend_point.insert`（`all/scripts.lua:7302`）：
   - 按 `P:nearest_nodes(pos)` 找最近节点，凡距离 < `path_width(pi) * 0.5` 的路径都 `set_defend_point_node(pi, ni)`（只覆盖各路径的**子路径 1**，因为 `subpath_indexes` 默认 `{1}`）；
   - 若实体带 `editor.exit_id`，则往 `store.level.locations.exits` 追加 `{pos, exit_id}`——**自定义 level 的 `insert_hero` 就靠这个**。
2. 扣命判定在 `all/systems/enemy.lua:136`：
   ```lua
   if end_node <= node_index and not P.path_connections[pi] and e.enemy.remove_at_goal_line then
   ```
   → **有 connections 的路径不会扣命**（它转去走下一段路），没有 connections 的路径走到 `path_end_node` 才扣 `lives_cost` 并加 `enemy.gold`。`remove_at_goal_line` 默认 true。
3. `defend_point_node` 还影响 `nodes_to_defend_point`（技能射程判定）与建塔合法性 margin，不放防御点会连带影响这两处。

## 五、出怪审查清单

> 常规做法：先按上面的确定性规则写一份「设计表」（每波：interval、各子波 delay/rest/path/兵种/数量），
> 用 `scripts/gen_waves_from_design.py` 一次吐出编译态 + 配置态两个文件（改数值只需改设计表重跑），
> 再用 `scripts/verify_wave_counts.py` 模拟编辑器算法，确认「配置重新生成」不会改变数量。

1. 编译态与 `_config.lua` 是否一致（编辑器改完有没有点「生成出怪」）。
2. `wave.path_index` 是否都在 `#paths` 范围内且 `active = true`；`spawn.path` 是否 ≤ 该组子路径数。
3. 每一组的实际出兵数：数 `max >= 1` 的条目数（**不是**条目总数，`max = 0` 是空档）。
4. 时间轴：把 `max = 0` 的 `interval` 累加还原成空档节奏，核对总时长是否等于编辑器填的「波长」。
5. **总扣命 vs `lives`**：Σ(数量 × `lives_cost`) 就是全漏时的扣命；测试图别贴着 `lives` 配数量。
6. 组数：只有 1 组时打完即结算，正式关要加够组数。
7. `connections` 距离复核（第三节）。
8. 出口贴图位置 vs 各路径实际终点——终点常在 `y < 0`（出屏），防御点旗子若放在 `y > 0` 会看到怪从旗子上方走过去，需进游戏确认观感。

## 六、改动后的固定流程

1. 改工作区副本 `KingdomRushDove/mods/local/<plugin>`；
2. 语法校验：`python .workbuddy/lua_syntax_check.py <改动文件...>`（ctypes 直连游戏自带 `lua51.dll`，需先 `os.add_dll_directory(工作区根目录)`，因为依赖同目录 `msvcr120.dll`）；
2.5 若改了关卡脚本（`data/levels/<plugin>.lua`）的逻辑，再跑一次功能级自测（如 `.workbuddy/test_late_wave_buff.py`）：语法通过 ≠ 逻辑生效，数值钩子有取整/幂等/时序三个易错点；
3. **同步到** `%APPDATA%\LOVE\kingdom_rush_dove\plugins\<plugin>`（游戏只读 AppData）；
4. `diff -r` 两副本确认一致，再进游戏实测。

## 七、地图背景图（自己画的整张地图大图）

把一张现成图片当作关卡底图，必须**四件套齐**，缺一件游戏里就是「背景空白 + 日志 `not a valid file`」：

1. 图片放 `<plugin>/assets/images/`（png / dds 都行；Android 端 `lib/klove/image_db.lua:471` 会自动优先 `.astc`、再退 `.png`）。
2. 新建 `<plugin>/assets/images/<图集名>.lua`：

```lua
return {
    <精灵名> = {
        a_name = "我的地图.png",          -- 实际图片文件名（含扩展名）
        size   = {1920, 1080},            -- 帧的**逻辑尺寸**（世界里画多大）；默认对齐本体口径
        trim   = {0, 0, 0, 0},
        a_size = {1920, 1080},            -- 图集页尺寸，喂给 G.newQuad
        f_quad = {0, 0, 1920, 1080},      -- 该帧在图片里占的源矩形
        alias = {},
    },
}
```

**三个尺寸字段的语义别搞混**（`lib/klove/image_db.lua:499-506` + `all/render_utils.lua:284`）：

| 字段 | 含义 | 约束 |
|------|------|------|
| `a_size` | 图集页尺寸，`G.newQuad(..., a_size)` 的分母 | 决定 UV；单帧页的真实像素**可以**与它不同 |
| `f_quad` | 源矩形 | 必须落在 `a_size` 内 |
| `size` | 帧的**逻辑尺寸**，渲染目的尺寸 = `size × ref_scale × sprite.scale` | 与 `f_quad` 不等 = 画面被拉伸 |

- `size` 默认就填 **1920 × 1080**（本体 `stage_N` 口径），此时 `size == f_quad`、无拉伸；
  想让背景比 16:9 再宽一点（更宽的屏幕不露边）就**只调 `size.x`**，`a_size`/`f_quad` 保持图片真实像素
  → 代价是画面被**水平拉伸** `size.x / f_quad.w`。例如 `size={1980,1080}` + 1920 宽的图 = 拉伸 3.1%，
  有效世界宽度从 1365 变 1408。
- **图片分辨率可以高于 `a_size`**：只要 `f_quad` 占满整页，`newQuad` 的 UV 就是 `(0,0)-(1,1)`，
  取样整张纹理，实际分辨率不一致**不影响正确性**、只影响清晰度与显存。
  实证：`Tropical_Loop`/`zhaozedixue` 的 `a_size=1920x1080`，而 `热带回环.png` / `沼泽地穴-1.dds`
  实际都是 3840×2160，游戏里显示正常（等于自带超采样）。
  ⚠ 多帧图集不适用这条——UV 是按 `a_size` 的分数算的，真实像素必须与 `a_size` 一致。

3. `data/levels/<plugin>_data.lua`：`entities_list` 里那个 `decal_background` 的
   `["render.sprites[1].name"] = "<精灵名>"`，`["render.sprites[1].z"] = 1000`（`Z_BACKGROUND`），
   `pos = v(512, 384)`（`all/templates.lua:120` 的基模板默认就是世界中心）；并注册图集：

```lua
plugin_required_textures = {
    <图集名> = { path = "<plugin>/assets/images", use_bytecode = false },
},
```

4. 可选：`_metadata.lua` 的 `thumbnail = "assets/images/我的地图.png"` → 自定义地图列表的预览图
   （`all/screen_custom_map.lua:123` 按 `.dds/.astc/.png/.jpg` 顺序探测，卡片会自动缩放适配）。

### 为什么这些字段是这些值

- **`path` 是相对 `plugins/` 根**，不是相对插件目录：`director:load_plugin_texture_groups`（`all/director.lua:619`）
  自己拼 `"plugins/" .. texture_group_info.path`。工作区里 `plugins` 根 = `KingdomRushDove/mods/local`。
- **注册 key（图集名）必须正好等于描述文件名（去 `.lua`）**：`image_db:preload_atlas`（`lib/klove/image_db.lua:464`）
  拼的是 `path .. "/" .. name .. ".lua"`。key 写错 = 找不到描述文件。
- **`use_bytecode = false`**：走 `I:load_atlas` 读 `.lua` 描述；`true` 会去找预编译字节码（自建图集没有）。
- **`size` 定世界里的缩放**：桌面端 `texture_size = "fullhd"`、`game.ref_res = TEXTURE_SIZE_ALIAS.ipad = 768`
  → `get_texture_scale` 给出 `768/1080 = 0.7111` 的 ref_scale → `size={1920,1080}` 对应有效绘制尺寸 **1365×768**。
  改 `size` 就是改背景在世界里的占位，先想清楚再动。

### 可见区域（作图前必看）

- `all/constants.lua:39` 把 16:9 上限注释掉了，**`MAX_SCREEN_ASPECT = 100`** → 宽屏是
  **横向多露出世界**，不是裁切世界。
- 于是：16:9 屏可见世界 = `768 × 16/9 = 1365` 宽 × 768 高，**正好等于背景的有效尺寸**，全图完整呈现；
- **4:3 屏只显示中间 1024 宽** → 背景左右各被切掉约 170 逻辑像素 = 源图 **左右各 ~240px（12.5%）**。
  画地图时把塔位、路径、出口这类关键内容留在中间，别贴左右边缘。

### 静态校验

`scripts/verify_level_bg.py <关卡entry> [...]`（纯 Python 解析 Lua 数据表，不依赖 lua51.dll）：
逐条模拟上面四步，对**工作区副本 + AppData 副本**各查一遍（10 项/份）。

```bash
python scripts/verify_level_bg.py SHEN_LIN_KONG_DI
# 反测已完工关卡，确认假设没跑偏：
python scripts/verify_level_bg.py Tropical_Loop BleakDune zhaozedixue
```

它额外断言：只有 `z == 1000` 的那个 `decal_background` 才是铺满全屏的主背景，
同模板高 z 的实体是贴花（如沼泽地穴的 `zhaozedixue_rock`，z=3100、310x111），尺寸随意。
并会把「图片真实像素 / `size` vs `f_quad` 的拉伸比 / 有效世界尺寸 / 与 16:9·4:3 可见区的差值」
直接打出来，改 `size` 前先跑一遍看数字。

`BODY_BG_SIZE`（1920×1080）、`REF_SCALE`（768/1080）、`VISIBLE_16_9`/`VISIBLE_4_3` 都定义在脚本顶部，
换分辨率档位只需改那几个常量。

### 环境坑（写这类校验脚本时会撞上）

- **`lua51.dll` 的 `io.open` 走 ANSI 代码页**（本机 ACP=936）→ 含中文的工作区路径（`王国保卫战Dove版`）
  在 Lua 里打不开；路径要按 GBK 编码才能用。可靠做法是**文件读写交给 Python**。
- `luaL_dostring` / `lua_pushstring` / `lua_isfunction` / `lua_pushcclosure` 里的 `lua_setglobal`
  在 Lua 5.1 都是**宏**，`lua51.dll` 不导出。
- **`ctypes` 注册 Lua 回调（`lua_pushcclosure`）后，回调里调任何 `lua_push*` 都会 AV**
  （`lua_gettop` 这类只读的反而正常）——别走 ctypes-callback 这条路，宁可纯 Python 解析数据表。
- Lua 5.1 允许**中文字节作裸标识符**（BleakDune 的 `废弃沙地 = { ... }` 能正常编译，已用本仓
  `lua51.dll` 实测），Python 解析器的 name 词法要写成 `[^\W\d]\w*`（`re.UNICODE`）。

