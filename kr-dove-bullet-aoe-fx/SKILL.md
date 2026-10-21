---
name: kr-dove-bullet-aoe-fx
description: 给《王国保卫战 Dove 版》的弹丸加"命中后范围伤害 / 落地地面特效 / 真实伤害"的薄包装范式——不改引擎、不复制基脚本。适用：自定义塔或英雄的子弹要做爆炸 AOE（`bullet.damage_radius` 基脚本根本不消费）、特殊弹要转真实伤害（DAMAGE_TRUE）、命中点要留地面印记（如兵营塔「火箭枪手」的 floor fx）、以及"每 N 发 / 每 N 轮触发一次强化弹"这类计数被动（粒度由调用点在循环内/外决定）。含基脚本薄包装写法、伤害入队口径、暴击污染坑、常驻图集核查、离线断言配方。触发词：子弹爆炸、弹丸范围伤害、damage_radius 无效、真实伤害、DAMAGE_TRUE、floor_fx 地面印记、瞄准靶心、特殊弹、每N发触发。
agent_created: true
---

# Dove 弹丸：范围伤害 / 真实伤害 / 落地特效

## 核心事实（先别急着改引擎）

- **`bullet.damage_radius` 不是通用的**：`all/components.lua:942` 只是组件默认值 0。真正消费它的只有写了这段逻辑的弹丸脚本（`all/scripts.lua:3136` 导弹、`:4236`、`:8146` 等）。基模板 **`scripts.shotgun.update`（`all/scripts.lua:3929`）完全不看 damage_radius** → 继承它的弹丸（含多数英雄枪弹、箭矢）写这个字段等于没写。**不要**去改引擎脚本，用薄包装。
- **真实伤害**：`all/constants.lua:108 DAMAGE_TRUE = 1`（独立位，与其它类型不重叠）。`U.calc_protection`（`all/utils.lua:1984`）`band(dt, DAMAGE_TRUE) ~= 0 → protection = 0` ⇒ 无视护甲与魔抗；`predict_damage` 得 `value * damage_factor`。伤害数字样式走 `health.lua:112` 第 15 档。**免疫按位判**（`health.lua:655`）→ 真实伤害不吃「物理免疫」这类分组免疫，只吃 `DAMAGE_ALL_TYPES`。
- 单发改类型是安全的：每次开火都是 `E:create_entity(tpl)` 新实例，改实例字段不会污染后续子弹（`level_up` 那类写模板才是全局的）。

## 薄包装写法（模板级，只影响这一枚弹丸）

```lua
-- 模板里：tt.main_script.update = scripts.my_bullet.update
scripts.my_bullet = {}

function scripts.my_bullet.update(this, store)
    local b = this.bullet
    local radius = b.damage_radius

    if not (radius and radius > 0) then
        return scripts.shotgun.update(this, store)   -- ⚠ 动态查表调用，单测才能换哨兵
    end

    local primary_id = b.target_id
    local impact = V.vclone(b.to)
    local dmin, dmax = b.damage_min, b.damage_max   -- 落点前快照

    scripts.shotgun.update(this, store)             -- 飞行 + 主目标直击 + mod + 暴击 全交给基脚本

    local primary = store.entities[primary_id]      -- 与基脚本同口径判命中
    if not (primary and primary.health and not primary.health.dead) then return end

    b.damage_min, b.damage_max = dmin, dmax         -- 复位：否则基脚本的暴击改分会污染爆炸数值

    local enemies = U.find_enemies_in_range_filter_off(impact, radius,
        b.damage_flags, bit.bor(b.damage_bans, F_FLYING))   -- 禁飞行传第 4 参

    if enemies then
        for i = 1, #enemies do
            local e = enemies[i]
            if e.id ~= primary_id then             -- 排除主目标，避免直击/爆炸双算
                queue_damage(store, SU.create_bullet_damage_without_pops(b, e.id, this.id))
            end
        end
    end

    if E:get_template(FLOOR_FX) and band(primary.vis.flags, F_CLIFF) == 0 then
        local fx = E:create_entity(FLOOR_FX)
        fx.pos.x, fx.pos.y = impact.x, impact.y
        fx.render.sprites[1].ts = store.tick_ts
        queue_insert(store, fx)
    end
end
```

`queue_damage` / `queue_insert` 在插件里自己写两行（它们不是 utils 的公开接口）：
`store.damage_queue[#store.damage_queue + 1] = d`（引擎每帧末交换处理）/ `simulation:queue_insert_entity(e)`。
**不要**自己 `queue_remove` 弹丸（基脚本已经做了）。

## 坑清单

1. **命中判定**：基脚本内部的 `target` 变量拿不到。用"基脚本返回后主目标是否仍存活"近似；目标瞬移/被 `F_RANGED` 禁标时会误判为命中，影响可忽略（弹丸本来就落在那儿）。
2. **伤害数值污染**：基脚本里的 `archer_precision` 暴击会改 `b.damage_min/max`（`all/scripts.lua:3973`）→ 爆炸必须用落点前快照覆盖回去，否则"暴击的那一发爆炸也变大"。
3. **AOE 不打伤害数字**：`SU.create_bullet_damage_without_pops` 故意清掉 pop（引擎 AOE 惯例，避免刷屏）。要数字就自己 `E.assign_damage`。
4. **`find_enemies_in_range_filter_off(origin, range, flags, bans)`**：`flags` 比 `e.vis.bans`、`bans` 比 `e.vis.flags` → **禁飞行把 `F_FLYING` 传第 4 参**。内部 `enemy_filter_simple` 还要求 `nav_path` 有效（离线单测必须打桩）。
5. **地面印记的帧归属要先查**：插件要用某帧前，先 `grep -la "<帧前缀>" _assets/kr1-desktop/images/fullhd/go_*.luac` 定位图集组。**在 `all/game.lua:30-63` 的常驻组里（`go_decals`/`go_enemies_common`/`go_editor`/`go_towers_group1..25`/`go_stage128`/`tower_holders`）就不用管**；否则得走 `required_textures`（游戏本体图集不能走 plugin 通道，见技能 `kr-dove-cross-level-resources`）。已验证：`rocket_gunners_tower_hit_fx_floor_0001..0025`（火箭枪手飞行普攻地面印记）在常驻 `go_towers_group19`。
6. **计数被动的「粒度」由调用点位置决定，不在计数器内部**：计数函数只认"被调用了几次"（`this._xxx = {a=0, b=0}`，**跨连发/跨目标不清零**；"每 N 次之后的下一发"= 周期 **N+1**，并给 `period < 1` 兜底，配置填 0 = 每次触发）。所以"每发"还是"每轮"完全取决于把 `next()` **放在哪**：
   - **每发** → 调用写在 `for si = 1, <连发数> do` **循环体内**（johnny_deadeye 的**霰弹**就是这样：每 4 发后的那 1 发 ×1.5 + 爆炸）。
   - **每整轮普攻** → 调用提到循环**之前**存局部 bool（`local round = next(this, "revolver")`），循环内 `if round then` → **该轮所有子弹一起生效**（johnny_deadeye 的**左轮**：攒满那轮六发全部转真实伤害 ×1.4）。
   ⚠ 同一个 `next()` 两种模式共用、粒度不同时，**务先把粒度写进注释**（这里踩过：先按每发实现、被用户否掉"左轮应该是五个整轮普攻"）。
   - 离线断言补一段**源码结构断言**（`io.open('mods/local/.../hero_scripts.lua')` + `find(..., true)` 比对位置）：断言"左轮调用出现在其 `for` 行之前"、"霰弹调用出现在其 `for` 行之后"、"调用各只出现 1 次"。比跑协程看行为省事、且直击粒度这个要害。
   - 阈值选成"连发数 − 1"就能让**每发**口径的特殊弹稳定落在每轮最后一发（左轮 6→5、霰弹 5→4）。

## 离线断言配方（不需要开游戏）

用技能 `kr-dove-offline-lua-harness` 的 `run_lua.py`。要点：

- 想只测包装层：**把 `scripts.shotgun.update` 换成哨兵**（记录调用次数，可选模拟暴击改 `b.damage_min/max`）。这要求包装里是 `scripts.shotgun.update(...)` 动态查表 —— 写成 local 捕获就测不了。
- 把 `U.find_enemies_in_range_filter_off` 换成**同语义桩**（`U.is_inside_ellipse` + `band(vis.bans, flags)`/`band(vis.flags, bans)` 过滤），同时**记录传参**断言半径/flags/bans/中心点。
- 把 `simulation.queue_insert_entity` 换成收集器，断言特效实体数量、`pos`、`render.sprites[1].name`（比 `template_name` 可靠）、`ts`、`scale`。
- 造几个敌人：主目标（在落点）、近处地面（应中）、远处地面（不应中）、近处飞行（不应中）；再跑一遍"主目标已死""主目标在悬崖""半径改小""缩放改成 2"的变体。
- 计数逻辑记得**挂到 script 表上**（`scripts.<name>.fn`，文件里再 `local fn = scripts.<name>.fn`），否则 local 函数无法断言。参考实现与 34 项断言：`.workbuddy/verify_deadeye_bullseye.lua`（工程 johnny_deadeye）。
