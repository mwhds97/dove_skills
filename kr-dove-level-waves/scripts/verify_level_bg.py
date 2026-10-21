"""自建关卡的「地图背景图」接入校验（纯 Python，不依赖 lua51.dll / 不启游戏）。

模拟引擎真实的加载链路（all/director.lua + lib/klove/image_db.lua）：

  1. director:load_plugin_texture_groups (all/director.lua:619)
       path = "plugins/" .. <_data.lua 里 plugin_required_textures[键].path>
       → path 是相对「plugins 根」的路径（工作区里 plugins 根 = KingdomRushDove/mods/local）
  2. image_db:preload_atlas (lib/klove/image_db.lua:451)
       group_file = <plugins 根>/<path>/<键>.lua
       → 键必须正好等于图集描述文件名（去后缀），否则报 not a valid file
  3. image_db:load_image_file (lib/klove/image_db.lua:630)
       f = <plugins 根>/<path>/<描述里每帧的 a_name>，扩展名须是 dds/png/jpg/astc
  4. screen_custom_map:scan_maps (all/screen_custom_map.lua:99)
       metadata.thumbnail → <插件目录>/<thumbnail>，按 .dds/.astc/.png/.jpg 顺序探测

顺带做一条会真崩游戏的静态检查：关卡脚本调 LU.insert_hero 时，必须有落点
（_data.lua 的 custom_spawn_pos 或带 editor.exit_id 的 decal_defend_point），
否则 all/level_utils.lua:470 索引 locations.exits 直接炸。

任何一环对不上，游戏里就是「背景空白 + 日志 not a valid file」。

用法:
    python .workbuddy/verify_level_bg.py                     # 默认查 SHEN_LIN_KONG_DI
    python .workbuddy/verify_level_bg.py Tropical_Loop BleakDune
"""

import os
import re
import struct
import sys

def _find_project():
    p = os.path.dirname(os.path.abspath(__file__))
    for _ in range(12):
        if os.path.isdir(os.path.join(p, "KingdomRushDove")):
            return p
        p = os.path.dirname(p)
    return os.environ.get("KR_DOVE_PROJECT", "")


PROJECT = _find_project()
if not PROJECT:
    raise SystemExit("找不到工程根（应含 KingdomRushDove 子目录）；请设 KR_DOVE_PROJECT")
WS = os.path.dirname(PROJECT)
KR6_ROOT = os.environ.get("KR6_SRC", os.path.join(WS, "Kingdom Rush Genesis"))
MAGICK = os.environ.get("MAGICK", r"D:\app\ImageMagick-7.1.2-Q16-HDRI\magick.exe")
ROOT = PROJECT
WS_PLUGINS_ROOT = os.path.join(ROOT, "KingdomRushDove", "mods", "local")
AD_PLUGINS_ROOT = os.path.join(
    os.environ.get("APPDATA", ""), "LOVE", "kingdom_rush_dove", "plugins"
)

SUPPORTED_EXT = (".dds", ".png", ".jpg", ".astc")
# 桌面端固定档位：params.texture_size = "fullhd"、game.ref_res = TEXTURE_SIZE_ALIAS.ipad = 768
# （all/constants.lua:57-63 + all/director.lua:143-151）→ 插件图集的 ref_scale = 768/1080
REF_RES = 768
FULLHD = 1080
REF_SCALE = REF_RES / FULLHD
# 本体背景帧口径：_assets/kr1-desktop/images/fullhd/go_stage01_bg.lua 的 stage_1
BODY_BG_SIZE = (1920, 1080)
# 16:9 / 4:3 屏可见的世界尺寸（宽 = 768 × 屏幕宽高比）
VISIBLE_16_9 = (REF_RES * 16 / 9, REF_RES)
VISIBLE_4_3 = (1024, REF_RES)


def image_pixels(path):
    """读图片文件的真实像素尺寸（png / dds）。读不出返回 None。"""
    try:
        with open(path, "rb") as f:
            head = f.read(32)
    except OSError:
        return None
    if head[:8] == b"\x89PNG\r\n\x1a\n" and head[12:16] == b"IHDR":
        return struct.unpack(">II", head[16:24])
    if head[:4] == b"DDS ":
        h, w = struct.unpack("<II", head[12:20])
        return (w, h)
    return None


# ────────────────────────── Lua 数据表字面量解析 ──────────────────────────


class LTable(dict):
    """Lua 表：数组部分落在整数键 1..n，带名键落在字符串键。"""

    def get(self, k, default=None):
        return dict.get(self, k, default)

    @property
    def array(self):
        return [self[i] for i in sorted(k for k in self if isinstance(k, int))]

    def __repr__(self):
        return "LTable(%s)" % dict.__repr__(self)


_TOKEN = re.compile(
    r"""
      (?P<ws>\s+)
    | (?P<llcmt>--\[\[.*?\]\])
    | (?P<lcmt>--[^\n]*)
    | (?P<str>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')
    | (?P<num>-?(?:0[xX][0-9a-fA-F]+|\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?))
    | (?P<name>[^\W\d]\w*)
    | (?P<punct>[{}\[\]=,;()])
    """,
    re.S | re.X | re.UNICODE,
)


def _unescape(raw):
    body = raw[1:-1]
    out, i = [], 0
    while i < len(body):
        c = body[i]
        if c != "\\":
            out.append(c)
            i += 1
            continue
        nxt = body[i + 1] if i + 1 < len(body) else ""
        simple = {"n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b", "f": "\f", "v": "\v",
                  "\\": "\\", '"': '"', "'": "'", "\n": "\n"}
        if nxt in simple:
            out.append(simple[nxt])
            i += 2
        elif nxt.isdigit():
            m = re.match(r"\\(\d{1,3})", body[i:])
            out.append(chr(int(m.group(1))))
            i += len(m.group(0))
        else:
            out.append(nxt)
            i += 2
    return "".join(out)


def parse_lua_table(text):
    """解析 `return { ... }` 形式的纯数据 Lua 文件，返回 LTable / 标量。"""
    toks = []
    pos = 0
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m:
            raise ValueError("无法切词，停在 %r" % text[pos:pos + 40])
        pos = m.end()
        kind = m.lastgroup
        if kind in ("ws", "llcmt", "lcmt"):
            continue
        toks.append((kind, m.group()))
    toks.append(("eof", ""))

    i = 0

    def peek():
        return toks[i]

    def take():
        nonlocal i
        t = toks[i]
        i += 1
        return t

    def expect(p):
        kind, val = take()
        if val != p:
            raise ValueError("期望 %r，实际 %r" % (p, val))

    def parse_value():
        kind, val = take()
        if val == "{":
            return parse_table()
        if kind == "str":
            return _unescape(val)
        if kind == "num":
            return float(val) if re.search(r"[.eE]", val) else int(val, 0)
        if val == "true":
            return True
        if val == "false":
            return False
        if val == "nil":
            return None
        if kind == "name":
            # 只支持 v(x, y) 这类构造调用，返回参数表
            nk, nv = peek()
            if nv == "(":
                take()
                args = []
                while True:
                    k2, v2 = peek()
                    if v2 == ")":
                        take()
                        break
                    if v2 == ",":
                        take()
                        continue
                    args.append(parse_value())
                return ("call", val, args)
            return val
        raise ValueError("无法解析的值 %r" % val)

    def parse_table():
        nonlocal i
        t = LTable()
        n = 0
        while True:
            kind, val = peek()
            if val == "}":
                take()
                return t
            if val in (",", ";"):
                take()
                continue
            # 带名键: name = value   /   [expr] = value
            if val == "[":
                take()
                key = parse_value()
                expect("]")
                expect("=")
                t[key] = parse_value()
                continue
            if kind == "name":
                save = i
                take()
                k2, v2 = peek()
                if v2 == "=":
                    take()
                    t[val] = parse_value()
                    continue
                i = save  # 回退，当成数组元素
            n += 1
            t[n] = parse_value()

    kind, val = take()
    if val == "return":
        return parse_value()
    i = 0
    return parse_value()


def load_lua(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return parse_lua_table(f.read())


# ────────────────────────── 校验 ──────────────────────────


class Report:
    def __init__(self):
        self.checks = 0
        self.fails = 0
        self.lines = []

    def check(self, ok, label, detail=None):
        self.checks += 1
        if ok:
            self.lines.append("  OK    " + label)
        else:
            self.fails += 1
            self.lines.append("  FAIL  " + label + (("  <--  " + str(detail)) if detail else ""))
        return ok

    def note(self, text):
        self.lines.append("  --    " + text)

    def head(self, text):
        self.lines.append(text)

    def flush(self):
        print("\n".join(self.lines))
        self.lines = []


def check_root(rep, plugins_root, tag, entry):
    rep.head("== %s ==" % tag)
    rep.head("   %s" % plugins_root)

    pdir = os.path.join(plugins_root, entry)
    if not os.path.isfile(os.path.join(pdir, "config.lua")):
        rep.note("（跳过：该目录下没有这个插件）")
        rep.flush()
        return

    data_path = os.path.join(pdir, "data", "levels", entry + "_data.lua")
    try:
        data = load_lua(data_path)
    except Exception as e:
        rep.check(False, "解析 %s_data.lua" % entry, e)
        rep.flush()
        return

    # ── 1. 背景实体指向哪个精灵 ──
    ents = data.get("entities_list") or LTable()
    bg_names = []
    if isinstance(ents, LTable):
        for e in ents.array:
            if isinstance(e, LTable) and e.get("template") == "decal_background":
                bg_names.append((e.get("render.sprites[1].name"), e))
    rep.check(len(bg_names) > 0, "存在 decal_background 背景实体")
    if not bg_names:
        rep.flush()
        return
    rep.note("decal_background 共 %d 个：%s" % (
        len(bg_names), ", ".join(str(n) for n, _ in bg_names)))

    # ── 2. 收集已注册的插件图集 ──
    prt = data.get("plugin_required_textures") or LTable()
    atlas_frames = {}   # sprite -> (frame, atlas_key)
    atlas_a_names = []  # (atlas_key, a_name, path)
    registered = [k for k in prt if isinstance(k, str)]

    for key in registered:
        info = prt[key]
        rel = info.get("path") if isinstance(info, LTable) else None
        if not rel:
            rep.check(False, "plugin_required_textures.%s.path 存在" % key)
            continue
        rep.check(info.get("use_bytecode") in (False, None),
                  "plugin_required_textures.%s.use_bytecode = false" % key,
                  "实际 %r（true 会去找编译态字节码而非 .lua 描述）" % info.get("use_bytecode"))
        atlas_path = os.path.join(plugins_root, rel, key + ".lua")
        if not rep.check(os.path.isfile(atlas_path),
                         "图集描述存在 %s/%s.lua" % (rel, key)):
            continue
        try:
            atlas = load_lua(atlas_path)
        except Exception as e:
            rep.check(False, "解析图集 %s.lua" % key, e)
            continue
        for sprite, frame in atlas.items():
            if not isinstance(frame, LTable):
                continue
            atlas_frames[sprite] = (frame, key)
            atlas_a_names.append((key, frame.get("a_name"), rel))

    if not registered:
        rep.note("plugin_required_textures 未注册任何插件图集（背景只能来自本体图组）")

    # ── 3. 背景精灵必须能在已注册图集里解析到 ──
    for nm, e in bg_names:
        # z = 1000 是 Z_BACKGROUND（all/constants.lua:75），也就是铺满全屏的那张主背景；
        # 同模板的其它实体（z 更高的贴花，如沼泽地穴的岩石）尺寸随意。
        is_main = e.get("render.sprites[1].z") == 1000
        if nm is None:
            rep.check(False, "decal_background 未设置 render.sprites[1].name")
            continue
        rep.check(nm in atlas_frames,
                  "%s背景精灵 %s 可在插件图集里解析" % ("主" if is_main else "贴花", nm),
                  "图集可用精灵: %s" % (sorted(atlas_frames)[:8] or "无"))
        if nm not in atlas_frames:
            continue
        frame, key = atlas_frames[nm]
        # ── 4. 图片文件真实存在且扩展名受支持 ──
        a_name = frame.get("a_name")
        rel = prt[key].get("path")
        img = os.path.join(plugins_root, rel, a_name)
        rep.check(os.path.isfile(img), "背景图片存在 %s/%s" % (rel, a_name))
        rep.check(str(a_name).lower().endswith(SUPPORTED_EXT),
                  "图片扩展名受支持（dds/png/jpg/astc）", a_name)
        # ── 5. 几何自洽 ──
        # 三个尺寸字段的语义（lib/klove/image_db.lua:499-506 + all/render_utils.lua:284）：
        #   a_size = 图集页（图片文件本身）的像素尺寸，直接喂给 G.newQuad
        #   f_quad = 该帧在图片里占的源矩形
        #   size   = 该帧在世界里的**逻辑尺寸**，渲染时 batch:add 目的尺寸就用它
        #            → size 与 f_quad 不等 = 画面被拉伸（size×ref_scale 才是有效世界尺寸）
        q, asz, sz = frame.get("f_quad"), frame.get("a_size"), frame.get("size")
        if all(isinstance(x, LTable) for x in (q, asz, sz)):
            qa, sa, za = q.array, asz.array, sz.array
            rep.check(qa[0] >= 0 and qa[1] >= 0
                      and qa[0] + qa[2] <= sa[0] and qa[1] + qa[3] <= sa[1],
                      "f_quad 落在 a_size 内",
                      "f_quad=%sx%s a_size=%sx%s" % (qa[2], qa[3], sa[0], sa[1]))
            px = image_pixels(img)
            full_page = (qa[0] == 0 and qa[1] == 0
                         and qa[2] == sa[0] and qa[3] == sa[1])
            if not px:
                rep.note("a_size=%s（%s 读不出像素，需人工确认）" % (sa, a_name))
            elif full_page:
                # f_quad 占满整页 → newQuad 的 UV 就是 (0,0)-(1,1)，取样整张纹理，
                # 实际分辨率与 a_size 不一致也不影响取样，只影响清晰度/显存。
                rep.note("a_size=%s，图片实际 %dx%d（f_quad 占满整页，UV=(0,0)-(1,1)，"
                         "取样不受影响）" % (sa, px[0], px[1]))
            else:
                # 多帧图集：UV 是按 a_size 的分数算的，真实像素必须对上
                rep.check(tuple(sa) == px, "a_size = 图片真实像素（多帧图集必须一致）",
                          "a_size=%s 实际图片=%s" % (sa, px))
            if (za[0], za[1]) != (qa[2], qa[3]):
                rep.note("size=%sx%s ≠ f_quad=%sx%s → 拉伸 水平×%.4f 垂直×%.4f"
                         % (za[0], za[1], qa[2], qa[3], za[0] / qa[2], za[1] / qa[3]))
            if is_main:
                eff_w, eff_h = za[0] * REF_SCALE, za[1] * REF_SCALE
                rep.note("主背景有效世界尺寸 %.0f×%.0f（size×ref_scale，ref_scale=%.4f）"
                         % (eff_w, eff_h, REF_SCALE))
                rep.note("对比：本体背景口径 size=%dx%d → %.0f×%.0f；"
                         "16:9 屏可见 %.0f×%.0f，4:3 屏可见 %dx%d"
                         % (BODY_BG_SIZE[0], BODY_BG_SIZE[1],
                            BODY_BG_SIZE[0] * REF_SCALE, BODY_BG_SIZE[1] * REF_SCALE,
                            VISIBLE_16_9[0], VISIBLE_16_9[1], VISIBLE_4_3[0], VISIBLE_4_3[1]))
                if eff_w - VISIBLE_16_9[0] > 0.5:
                    rep.note("比 16:9 可见区宽 %.0f（左右各多出 %.0f，更宽的屏幕也不会露边）"
                             % (eff_w - VISIBLE_16_9[0], (eff_w - VISIBLE_16_9[0]) / 2))
            else:
                rep.note("贴花 %s 尺寸 %sx%s（不作主背景口径要求）" % (nm, za[0], za[1]))

    # ── 6. 英雄出生点：level:update 里调 LU.insert_hero 就必须要有个落点 ──
    # 崩溃链：all/systems/level.lua:118（有 _data.lua 就把 locations 清成 {}）
    #   → all/level_utils.lua:470 `pos = store.level.locations.exits[1].pos`
    #   → attempt to index field 'exits' (a nil value)
    # 两条生路（二选一，原版关卡也是这么分的）：
    #   a) _data.lua 里写 custom_spawn_pos={{pos=v(x,y)},…}（level49/101~137 口径）
    #   b) entities_list 里有带 ["editor.exit_id"] 的 decal_defend_point
    #      → all/scripts.lua:7302-7330 的实体脚本会自己把 locations.exits 建起来
    script_path = os.path.join(pdir, "data", "levels", entry + ".lua")
    if os.path.isfile(script_path):
        with open(script_path, "r", encoding="utf-8-sig", errors="replace") as f:
            script = f.read()
        if re.search(r"\binsert_hero\s*\(", script):
            csp = data.get("custom_spawn_pos")
            exits = sum(
                1 for e in ents.array
                if isinstance(e, LTable) and e.get("editor.exit_id")
            ) if isinstance(ents, LTable) else 0
            if csp:
                rep.check(True, "英雄出生点：_data.lua 里写了 custom_spawn_pos")
            else:
                rep.check(exits > 0,
                          "英雄出生点：无 custom_spawn_pos，靠 decal_defend_point 建 exits",
                          "既没有 custom_spawn_pos 也没有带 editor.exit_id 的 "
                          "decal_defend_point → locations.exits 恒为 nil，"
                          "选中英雄进关必崩 (level_utils.lua:470)")
            rep.note("关卡脚本 %s.lua 调用了 LU.insert_hero；custom_spawn_pos=%s，"
                     "带 exit_id 的 decal_defend_point=%d"
                     % (entry, "有" if csp else "无", exits))
        else:
            rep.note("关卡脚本未调用 LU.insert_hero（英雄相关崩溃风险不适用）")

    # ── 7. metadata.thumbnail（自定义地图列表的预览图）──
    meta_path = os.path.join(pdir, "data", "levels", entry + "_metadata.lua")
    if os.path.isfile(meta_path):
        try:
            meta = load_lua(meta_path)
        except Exception as e:
            rep.check(False, "解析 %s_metadata.lua" % entry, e)
            meta = None
        if isinstance(meta, LTable) and meta.get("thumbnail"):
            thumb = meta.get("thumbnail")
            base = re.sub(r"\.[^.]*$", "", thumb)
            found = next((ext for ext in SUPPORTED_EXT
                          if os.path.isfile(os.path.join(pdir, base + ext))), None)
            rep.check(found is not None, "metadata.thumbnail 可被列表探测到 %s" % thumb)
        else:
            rep.note("metadata.thumbnail 未设置（列表无预览图，不影响关内背景）")

    rep.flush()


def main():
    entries = sys.argv[1:] or ["SHEN_LIN_KONG_DI"]
    rep = Report()
    for entry in entries:
        check_root(rep, WS_PLUGINS_ROOT, "工作区开发副本 KingdomRushDove/mods/local", entry)
        check_root(rep, AD_PLUGINS_ROOT, "AppData plugins（游戏实际读这里）", entry)
        rep.head("")
    print("共 %d 项检查，%d 项失败" % (rep.checks, rep.fails))
    sys.exit(1 if rep.fails else 0)


if __name__ == "__main__":
    main()
