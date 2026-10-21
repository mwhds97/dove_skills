---
name: kr-remaster-bytecode-decompile
description: 反编译《王国保卫战》重制版（KR1/KR2/KR4 等 Ironhide Lua 游戏）的 LuaJIT 字节码 .lua 文件拿回可读源码。适用：给 `<工作区>\Kingdom Rush` 这类重制版目录查本体逻辑、挖英雄/塔/敌人数据、定位本体缺陷。触发词：反编译、字节码、LuaJIT、KR1 重制版、找英雄数据、本体源码。
agent_created: true
---

# KR 重制版 LuaJIT 字节码反编译

## 背景

> 路径约定：`<工作区>` = 存放各版本 KR 目录的父目录（本项目为 `C:\Users\29140\Desktop\qwe`）。

`<工作区>\Kingdom Rush`（KR1 重制版，带英雄系统）及 Dove 版本体目录里，所有 `.lua` 实为 **LuaJIT 字节码**（文件头 `\x1bLJ`，未 strip、带调试信息）。字符串常量明文可读，数值和结构需要反编译。

⚠ **例外（2026-10-15 实证）**：`<工作区>\Kingdom Rush Genesis`（KR6，含 `kr6/`+`all/`+`sequels/`）的 `.lua` 是**明文源码**（文件头 `EF BB BF` BOM + `-- chunkname` 注释），**不需要反编译**；对它跑 luajit-decompiler-v2 会静默失败（exit 1、output 无产物）。**判据**：`head -c 4 <文件> | xxd` 看是不是 `\x1bLJ`。

## 工具（已就位，勿重下）
- **反编译器**：`<Dove工程>\.workbuddy\ljdv2\luajit-decompiler-v2.exe`（`<Dove工程>` = `<工作区>\王国保卫战Dove版`）
  （marsinator358/luajit-decompiler-v2，release Mar_24_2024，287KB 单文件，实测对 KR1 重制版全部文件成功）
- 用法：**静默无输出**，`cd` 到工作目录后 `./luajit-decompiler-v2.exe "<字节码文件>"`，结果写到 `./output/<同名>.lua`；传文件夹则递归。成功与否看 output 目录里有没有产物。
- ⚠⚠ **cwd 不能是中文路径**（2026-10-21 实测）：在 `王国保卫战Dove版/.workbuddy/...` 下跑，工具 `exit 0`
  但 `output/` **是空的**、一句错都不报；把文件拷到纯英文目录（`/c/tmp/xxx`）后立刻成功。
  判据：`find . -name "*.lua" -newermt "-1 minutes"` 有没有产物 —— **别信 exit code**。
  工具会自己建 `output/`，不用预先 mkdir（预先建也不影响）。
- 注意：本机 git 全局配置把 github.com 重写到 `github.91chi.fun`（已死）。要下 GitHub 资源别用 `git clone`，用 `curl -sL https://codeload.github.com/<owner>/<repo>/zip/refs/heads/<branch>` 拉 tarball。

## 流程
1. **找目标**：字节码是二进制，Grep 工具目录遍历会静默跳过 → 用 Bash `grep -rlia "关键词" <目录>`（`-a` 当文本）先定位文件。
2. **反编译**：对命中的文件逐个跑工具，产物移到分析目录：
   ```bash
   cd <workdir> && ./ljdv2/luajit-decompiler-v2.exe "<文件>" && mv output/<名>.lua <产物目录>/<名>.decompiled.lua
   ```
3. **读数据**：反编译产物是合法 Lua 源码，直接 Grep/Read。模板字段 `RT("名","基类")`、子弹 `bullet.damage_min/max`、光环 `aura.*`、技能 `hero.skills.*`、行为脚本在 `scripts.<名>.update/level_up`（永续协程，含 `::label::` goto，LuaJIT 合法）。
4. **动画/贴图**：帧段 from/to/prefix 在 `kr1/data/game_animations.lua`；图集定义在 `_assets/<平台>/images/<组>/go_*.lua`；字符串表在 `_assets/<平台>/strings/en.lua`（也是字节码，同样反编译）。

## 坑
- **不要用 python ljd**（AzurLaneTools/ljd 等 fork）：rawdump 解析能过，但 ast builder 对 KR1 的主原型必崩（`AssertionError` / `_build_warp` IndexError），pseudoasm writer 也不稳。marsinator358 的 C++ 版没有这些问题。
- 产品页 `README` 说 404 时是分支名不对（有的仓库 master 有的 main），先 `api.github.com/repos/<owner>/<repo>` 查 `default_branch`。
- KR1 重制版反编译产物较大（game_templates ≈ 1MB），Grep 定位行号再局部 Read，别整读。
- **图集帧元数据要读反编译文本版，别想让 lua 直接把 `.luac` 跑出来**：Dove 的 `_assets/**/images/**/<图集>.luac` 用 `loadfile`/`luaL_loadfile` 载进来执行，得到的是**返回空**的 chunk（`select('#', f()) == 0`，真实加载走引擎自己的通道），所以"dump 帧表"这条路走不通。改用工具反编译出的文本版 `<产物>/<图集>.lua`：
  `{ count = N, keys = { "帧名", … }, values = { { a_name, f_quad = {x,y,w,h,tex_w,tex_h}, trim = {x,y}, ref_scale, size = {w,h} }, … } }`，**keys 与 values 同序**（按 index 取）。
  ⚠ `values` 里的条目是**位置值元组**，没有 `a_name = …` 这种命名键 —— 解析要按位置（第二个成员是 `f_quad`、第三个是 `trim`、第四个是 `ref_scale`、第五个是 `size`），用"按键名 find"会全军覆没。
  现成工具：`.workbuddy/dump_atlas_frames.py <反编译图集.lua> <图集 png/dds> <输出目录> <帧名…>` —— 打印元数据并裁出该帧以便肉眼确认。⚠ 里面 ImageMagick 路径要写 **Windows 形式**（`D:/app/ImageMagick-7.1.2-Q16-HDRI/magick.exe`），原生 Python 不认 MSYS 的 `/d/...`。
- 英雄数据关键位置（KR1 重制版）：模板 `kr1/game_templates.lua`（`RT("hero_xxx","hero")`）、行为 `kr1/game_scripts.lua`（`scripts.hero_xxx`）、成长/技能数值都在模板内 `hero.level_stats` / `hero.skills`。

## ⭐ 字符串表（`_assets/<平台>/strings/<lang>.lua`）的正确读法

**只想要键值对时，别急着反编译 —— 它慢**：`luajit-decompiler-v2.exe` 跑 265KB 的 `strings/en.lua`
**超过 2 分钟**（前台 Bash 会超时被杀）⇒ 要么 `run_in_background`，要么直接抽常量（多数场景够了）。

**扫「字符串常量」有两个方向相反的坑**（2026-10-03 抽 `HERO_*` 时连踩）：

| 起串条件 | 后果 |
|---|---|
| `0x20-0x7E or >=0xC2` | 能正确断在 LuaJIT 操作码上，**但 UTF-8 续字节 0x80–0xBF 被切断** ⇒ 中文全碎（抽 zh-Hans 候选 = 0 个） |
| `0x20-0x7E or >=0x80` | 续字节保住了，**但操作码 0x80–0xFF 也被当正文** ⇒ 常量互相粘连，键名被隔壁数据吞掉（`HERO_*` 键数从 32 掉到 0） |

✅ **正确规则**：**只在 `0x20-0x7E` 或 `>=0xC2` 处起串**；**已起串后允许 `0x20-0x7E` 或 `>=0x80` 续**；
最后用 `bytes.decode('utf-8')` + 长度 ≥2 过滤。

```python
def konst(p):
    b = open(p,'rb').read(); out=[]; run=bytearray()
    def fl(r):
        if len(r) >= 2:
            try: out.append(bytes(r).decode('utf-8'))
            except Exception: pass
    for c in b:
        if run:
            if 0x20 <= c <= 0x7e or c >= 0x80: run.append(c)
            else: fl(run); run = bytearray()
        else:
            if 0x20 <= c <= 0x7e or c >= 0xc2: run.append(c)
    fl(run); return out
```

**⭐⭐ 要判断「某个键到底存不存在」，别用自己的扫描器 —— 直接 `grep -c "<KEY>" <文件>` 扫原始字节。**
它跟过滤器无关，是唯一不会自欺的判据。（本次"中文串表里有没有那 7 位英雄"就是靠 `grep -c` 定案的。）

**取「键 → 值」⭐⭐ 按 ULEB128 长度前缀精确切，别启发式**：值紧跟键，中间隔一个 ULEB128 长度前缀
（1–2 字节，小端 7-bit）。**按长度切值就一个垃圾字节都不会粘**；启发式"读到不可打印为止"在长度 ≥128 时
会把后续常量首字节粘到值尾（值尾多出 `CRED` / `OMI` / `SETT` 之类垃圾），还会把首字母吞掉。

```python
import re
def uleb(buf, i):
    n = 0; shift = 0; hdr = 0
    while True:
        b = buf[i]; i += 1; hdr += 1
        n |= (b & 0x7f) << shift
        if b < 128: break
        shift += 7
    return n, hdr

m = re.search(rb'HERO_VIPER_DESCRIPTION(?![A-Z])', data)  # data = open(p,'rb').read()
n, hdr = uleb(data, m.end())
val = data[m.end()+hdr : m.end()+hdr+n].decode('utf-8')   # 精确到字节
```

⚠ 键名后加 `(?![A-Z])` 负向断言：`HERO_VIPER_DESCRIPTION` 会前缀命中更长键（如带 `_EXTRA` 的），
不排除会匹配错位置。

## ⭐ 英雄名单怎么数（KR1 重制版 / ReBBBorn）

- ⚠ **别用 `game_scripts*.lua` 里的 `hero_*` 字符串当名单**：`game_scripts_2/3.lua` 是**多作品共享引擎脚本**，
  塞着 KRF/KRO/KRV 的英雄（`alric` `mirage` `arivan` `lilith` `wilbur` `lynn` `faustus` `catha` `phoenix`
  `xin` `durax` `bolverk` `bravebark` `bruce` `regson` `veznan` …）+ 通用原型（`pirate` `wizard` `monk` …）。
- ✅ **权威名单 = 英雄殿堂 UI 模板的立绘项**：
  `grep -oa "portrait_hero_[a-z0-9_]*" kr1-desktop/data/kui_templates/hero_room_view.lua | sort -u`
  （KR1 v5.6.09 + ReBBBorn v3.0 = **20 条**：官方 13 + 重生新增 7）
- ✅ **交叉验证**：`grep -c "HERO_<X>_NAME" _assets/kr1-desktop/strings/en.lua` == 1，
  且 `_assets/kr1-desktop/images/fullhd/go_hero_<X>.lua` 图集存在。
- ⚠ 串表里英雄只有 `HERO_<X>_NAME` / `_SPECIAL` / `_DESCRIPTION`；另有几个 `HERO_*_NAME` 是**召唤物**不是英雄
  （`ARCHER_WILDCAT`、`MAGE_SHADOW`、`VIKING_ANCESTOR`）—— 计数时要剔掉。
- ⚠⚠ **mod 新增的英雄常常只有 `en.lua` 有串**（zh-Hans `grep -c` = 0）⇒ 移植时**中文文案必须自撰**。
- ReBBBorn 相关位点：`kr1/upgrades.lua`（**箭塔弹丸科技白名单**，逐英雄一段 —— 某英雄没出现，通常说明
  他的攻击不是弹丸）、`kr1/balance/rebbbalanced.lua`（ReBBBalanced 平衡表）、
  `kr1-desktop/data/kui_templates/hero_room_view.lua` + `screen_map_hero_room.lua`、
  `_assets/kr1-desktop/sounds/{extra,groups,sounds}.lua`。
