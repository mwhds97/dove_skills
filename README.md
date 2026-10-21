# Dove 插件开发技能包

15 个技能，约 7100 行踩坑记录 + 21 个脚本，外加 `memory/` 下的项目级长期约定。
**纯 Markdown + Python，离线可读、可直接跑**，不依赖任何特定工具。

| 我想…… | 去哪 |
|---|---|
| 查某个功能怎么做 | 第三节的分层表，找到对应 `SKILL.md` |
| 查这条规则/坑的来历 | 约定里留的索引，再翻历史开发日志（按日期） |
| 跑校验、生成、拆图 | 第四节的脚本速查 |
| 只想看"绝对不能犯的错" | 第七节，六条硬结论 |

> 包里还留着 `sync_skills.py` 和 `SKILL.md` 头部的 `agent_created` 这类痕迹，是导出时带出来的。别人的机器上没有对应环境，**一律可以忽略** —— 见第零节。

---

## 零、如果你不用 WorkBuddy（先读这段）

这一包**不依赖任何特定助手或工具**：

- 15 个目录就是普通文件夹，每个里面一个 `SKILL.md`（纯 Markdown），有的带 `scripts/`（纯 Python）。
- `SKILL.md` 开头的 `---` 块（`name` / `description` / `agent_created`）是给助手做「什么时候该读我」的匹配用的。**人读直接跳过它，从下面的 H1 标题开始看**，正文没有任何工具绑定。
- 脚本只要求 `python3`；离线跑引擎那个（`run_lua.py`）额外要游戏自带的 `lua51.dll` 和 `lupa` 包，属可选项。
- **不需要安装、不需要联网同步**：所有内容已经在这里了。`sync_skills.py` 只对"手里有源技能库副本的人"有意义，其他人当它不存在即可；`memory/` 下的约定同理，是自带的副本。
- 唯一跟工具有关的信息是 `memory/README.md` 末尾那个「8000 字符」附录（某个助手读文件的上限）。用别的工具可以忽略。

## 一、这目录是什么，不是什么

- **是**：可离线查阅的踩坑记录 + 能直接跑的校验脚本。
- **不是**：游戏插件。`mods/` 根本不在插件扫描路径上 —— `plugin/all/plugin_paths.lua:6`
  写的是 `LOCAL_PLUGINS_DIR = "plugins"`（指向 AppData 的 `plugins/`），所以放这里不会被加载，也不刷 log。
  （即便误放进扫描目录，`list_plugin_entries`（同文件 `:95-117`）遇到没有 `config.lua` 的目录只会
  `log.error("跳过不是插件的目录")`；真正 `error()` 的只有「缺 entry 字段」和「目录名 ≠ entry」两种。）

## 二、路径约定

脚本**不再写死绝对路径**，改成「自动探测工程根 + 环境变量覆盖」：

| 占位符 | 含义 |
|---|---|
| `<工作区>` | 各版本 KR 目录的父目录，例如 `D:\游戏\qwe`（同级的 `Kingdom Rush Genesis`、`base` 都在这层） |
| `<Dove工程>` | `<工作区>\王国保卫战Dove版` |
| `<技能包>` | 本目录（`KingdomRushDove\mods\dove_skills`） |

探测逻辑：从脚本所在目录向上最多 12 层，找**含 `KingdomRushDove` 子目录**的那一层。
所以放在本目录下零配置即用；挪到工程外则需设环境变量：

| 变量 | 默认 | 用途 |
|---|---|---|
| `KR_DOVE_PROJECT` | 自动探测 | 指 `<Dove工程>`，探测失败时必设 |
| `KR6_SRC` | `<工作区>\Kingdom Rush Genesis` | KR6 素材/模板源码根 |
| `MAGICK` | `D:\app\ImageMagick-7.1.2-Q16-HDRI\magick.exe` | 图集拆图用 |

> ⚠ Python 不认 Git Bash 的 `/c/...` 风格 —— 传路径一律用 `C:/...`，否则 `FileNotFoundError`。

## 三、15 个技能（按工作流分五层）

| 技能 | 层 | 干什么 | 规模 |
|---|---|---|---|
| `kr-remaster-bytecode-decompile` | 取数 | 反编译 KR1/KR2/KR4 的 LuaJIT 字节码；先判 `\x1bLJ` 文件头（KR6 是明文，别反编译） | 115 行 |
| `kr-dove-enemy-data` | 取数 | 按关卡号/模板名出敌方单位全字段表 | 78 行 + `extract_enemies.py` |
| `kr-dove-tech-tree-data` | 取数 | 四棵本体科技树的 key / 中文名 / 等级 / 价格 | 106 行 |
| `kr-dove-tower-port` | 移植 | FL7.5 塔移植为 Dove 插件（动画 loop 参数、目标 API 签名、`damage_hooks`） | 1299 行 |
| `kr-dove-kr6-powers-port` | 移植 | KR6/KR5/KR3/KR2 法术迁入 `kr6_powers`，13 法术；改源版本口径 + 四硬差异 | 1415 行 |
| `kr-dove-ui-panel` | 表现 | 手写 UI 面板 + 复用 KR6 图集；含 PIL 离线出图与布局自检 | 936 行 + 8 脚本 |
| `iron-marines-hero-port` | 移植 | Unity 素材整链移植（UnityPy → ilspycmd → Dove）；mod 叠层真伪、英雄 UI 图三路线 | 305 行 |
| `kr-dove-stage-hero-port` | 移植 | 舞台英雄转局外可选英雄；花名册三处注入、经验三件套 | 67 行 |
| `kr-dove-tavern-add-unit` | 移植 | 酒馆新增召唤单位的 7 触点 checklist | 63 行 |
| `kr-dove-mobile-tower` | 移植 | 塔改「可点调集、边走边打」；`motion/nav_rally/nav_grid` 三件套 | 487 行 |
| `kr-dove-level-waves` | 关卡 | 波次帧语义、`DELAY_SPREAD`、路径汇入、自绘地图背景四件套 | 502 行 + 5 脚本 |
| `kr-dove-cross-level-resources` | 表现 | 跨关复用模板/特效的强制加载与防卸载；动画键两侧逐字命中 | 377 行 + 3 脚本 |
| `kr-dove-bullet-aoe-fx` | 表现 | 弹丸 AOE / 真实伤害 / 落地印记的薄包装（`damage_radius` 基脚本不消费） | 87 行 |
| `kr-dove-plugin-config` | 工程 | 游戏内可改数值的配置面板；三档划分 + 逐键探针 | 621 行 + 1 脚本 |
| `kr-dove-offline-lua-harness` | 工程 | 用自带 `lua51.dll` 不开游戏跑真引擎断言 | 616 行 + `run_lua.py` |

## 四、脚本速查

| 脚本 | 位置 | 跑法 |
|---|---|---|
| `lua_syntax_check.py` | `kr-dove-level-waves/scripts/` | `python lua_syntax_check.py <a.lua> [b.lua...]` |
| `verify_level_bg.py` | 同上 | `python verify_level_bg.py <关卡名>`（默认 SHEN_LIN_KONG_DI） |
| `verify_wave_counts.py` | 同上 | `python verify_wave_counts.py` |
| `gen_waves_from_design.py` | 同上 | 生成 Tropical_Loop 16 波（写 dev + AppData 两侧） |
| `run_lua.py` | `kr-dove-offline-lua-harness/` | `python run_lua.py <游戏目录> <.lua>` |
| `verify_config_mapping.py` | `kr-dove-plugin-config/` | `python verify_config_mapping.py <插件目录> --balance scripts/balance.lua` |
| `check_kr6_frames.py` | `kr-dove-ui-panel/scripts/` | 查帧名是否真存在于 KRAB 图集 |
| `_krab_check.py` / `_krab_list.py` | 同上 | 解析 `.bin` KRAB 索引（离线 love_stub 不加载本体图集，静态 grep 会假阴性） |
| `extract_enemies.py` | `kr-dove-enemy-data/scripts/` | 出第 17/37 关敌方数据 JSON |

## 五、同步脚本（只对维护者有意义）

> 你手上没有"源技能库"的话，**整节跳过** —— 本包内容自足，不需要跑任何同步。

`sync_skills.py` 的默认源是 `%USERPROFILE%\.workbuddy\skills\`（可用 `--src` 改），只处理上面 15 个
（白名单写死在 `SKILLS`），**对本目录的 `README.md` / 自身 / 其他技能一概不碰**：

1. 逐个技能比对源与副本（只比内容，忽略 `__pycache__` / `*.pyc`）
2. 有差异则**先删副本目录、再整体拷贝** ⇒ 源里删掉的附件这里也会消失，不留残骸
3. 源里不存在的技能**跳过并告警**，不删本地副本（防误清空）
4. 拒绝在盘符根目录执行
5. 技能刷完后接着刷 `memory/项目级长期约定.md`（字节比对，一致就 `[same]`）；
   `--skip-memory` 可跳过，`--project <路径>` 可显式指定工程根

新增技能时，把目录名加进 `SKILLS` 白名单即可。

## 六、长期约定（`memory/`）

技能管**怎么做**，约定管**不许怎么做**。冲突时以约定为准：

| 文件 | 内容 | 规模 |
|---|---|---|
| `memory/项目级长期约定.md` | 本工程的引擎硬规则、插件范式、移植口径 | 8000 字符 |

**这份是完整的**，拿到手就能读，不用去找什么原件。它由开发者在自己环境里维护（原文是工程的 `MEMORY.md`），每次同步时整份覆盖过来。

- 维护者改约定请改原文再跑 `sync_skills.py`；这里直接改会被下次同步覆盖。
- 为什么会"整份覆盖"而不是追加：原文已经顶在**单文件读取上限边缘**（8000 字符，某助手注入上下文的截断阈值），再加一条就会吃掉末尾经验，所以这里同时存着一份备份。细则见 `memory/README.md` 附录。
- 逐日日志（34 个 / 1.2 MB）**没有复制**：它每天都在长，查证据按关键字去开发者工程里 grep。
- 详见 `memory/README.md`。

## 七、几条最容易忘的硬结论

- Mod 加载早于 GUI 类定义 ⇒ `rawget` 前必须 `require("game_gui")`；**绝不** require `all-desktop/screen_map`。
- `db_atlas` 是单表、后加载者覆盖 ⇒ 插件帧名必须独占前缀（现有约定 `kr6p_`）。
- 动画键查不到只 `log.error` 后**渲染成隐形、不崩** ⇒ 只能靠 `check_kr6_frames.py` 提前抓。
- `armor/magic_armor` 在 Dove 是 **0~1 比例**，填 40 会被夹成 1.0 = 完全免疫。
- 所有 CD 都要乘 `tower.cooldown_factor`。
- 回血没有 `U.heal`，直接改 `health.hp` + `km.clamp(0, hp_max, hp)`。
