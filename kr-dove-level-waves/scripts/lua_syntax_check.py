import ctypes, os, sys

import os

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
os.add_dll_directory(ROOT)
lua = ctypes.CDLL(os.path.join(ROOT, "lua51.dll"))

lua.luaL_newstate.restype = ctypes.c_void_p
lua.luaL_loadstring.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
lua.luaL_loadstring.restype = ctypes.c_int
lua.lua_tolstring.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_size_t)]
lua.lua_tolstring.restype = ctypes.c_char_p
lua.lua_close.argtypes = [ctypes.c_void_p]
lua.lua_settop.argtypes = [ctypes.c_void_p, ctypes.c_int]

files = sys.argv[1:]
bad = 0
for f in files:
    src = open(f, "rb").read()
    # strip UTF-8 BOM if present
    if src.startswith(b"\xef\xbb\xbf"):
        src = src[3:]
    L = lua.luaL_newstate()
    if not L:
        print("FAIL  cannot create lua_State"); bad += 1; continue
    rc = lua.luaL_loadstring(L, src)
    name = f.replace(ROOT + "\\", "")
    if rc == 0:
        print("OK    " + name)
    else:
        n = ctypes.c_size_t()
        msg = lua.lua_tolstring(L, -1, ctypes.byref(n))
        print("FAIL  " + name + "\n      " + (msg or b"").decode("utf-8", "replace"))
        bad += 1
    lua.lua_close(L)

print("\n%d file(s), %d failed" % (len(files), bad))
sys.exit(1 if bad else 0)
