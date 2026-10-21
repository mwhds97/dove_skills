"""用游戏自带的 lua51.dll（LuaJIT 2.1）跑离线 Lua 脚本。

为什么不用 luajit.exe：本机没有 luajit 可执行文件，但游戏根目录有 lua51.dll。

为什么要 os.chdir 到游戏目录：lua 的 require / io.open 走 C 运行时的 ANSI 路径解析，
含中文的绝对路径（本工程路径带「王国保卫战Dove版」）会打不开；相对路径由 Windows
内核按进程 CWD 解析，不受代码页影响。

为什么脚本内容由 Python 读进来再 luaL_loadbuffer：这样就**不受 cwd 限制**——
脚本可以放在 .workbuddy/ 下，chunkname 用相对路径（traceback 里能和 require 对得上）。

用法：
  python .workbuddy/run_lua.py <游戏目录> <.lua 脚本> [args...]
"""

import ctypes
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _find_dll(cwd):
    """lua51.dll 可能放在游戏目录、其上一级，或 skill 目录的上一级。

    实测踩过：dll 在「王国保卫战Dove版/lua51.dll」而游戏目录是它的子目录
    KingdomRushDove/，只按 skill 上一级找会 FileNotFoundError。
    """
    cands = [
        os.path.join(cwd, "lua51.dll"),
        os.path.join(os.path.dirname(cwd), "lua51.dll"),
        os.path.join(ROOT, "lua51.dll"),
    ]
    for c in cands:
        if os.path.exists(c):
            return os.path.abspath(c)
    return os.path.join(os.path.dirname(cwd), "lua51.dll")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2

    cwd = os.path.abspath(sys.argv[1])
    # ⚠ 脚本路径必须在 chdir 之前绝对化，否则传相对路径会 FileNotFoundError
    script = os.path.abspath(sys.argv[2])
    extra = sys.argv[3:]
    os.chdir(cwd)

    with open(script, "rb") as f:
        source = f.read()

    try:
        chunkname = os.path.relpath(script, cwd).replace("\\", "/")
    except ValueError:
        chunkname = os.path.basename(script)
    if chunkname.startswith(".."):
        chunkname = "@" + os.path.basename(script)
    else:
        chunkname = "@" + chunkname

    L = ctypes.CDLL(_find_dll(cwd))
    L.luaL_newstate.restype = ctypes.c_void_p
    L.luaL_openlibs.argtypes = [ctypes.c_void_p]
    L.lua_pushstring.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    L.lua_pushstring.restype = None
    L.lua_pcall.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int]
    L.lua_pcall.restype = ctypes.c_int
    L.lua_tolstring.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_size_t)]
    L.lua_tolstring.restype = ctypes.c_char_p
    L.lua_gettop.argtypes = [ctypes.c_void_p]
    L.lua_gettop.restype = ctypes.c_int
    L.luaL_loadstring.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    L.luaL_loadstring.restype = ctypes.c_int
    L.luaL_loadbuffer.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p]
    L.luaL_loadbuffer.restype = ctypes.c_int

    S = ctypes.c_void_p(L.luaL_newstate())
    L.luaL_openlibs(S)

    def last_error():
        n = L.lua_gettop(S)
        out = L.lua_tolstring(S, n, None)
        return (out or b"<no message>").decode("utf-8", "replace")

    # 游戏代码（version.lua）读全局 arg[0]：官方 luajit 解释器会自动设，这里补上
    rc = L.luaL_loadstring(S, b"arg = { [0] = ... }")
    if rc != 0:
        print("[run_lua] prelude error: " + last_error())
        return 1
    L.lua_pushstring(S, chunkname.encode("utf-8"))
    if L.lua_pcall(S, 1, 0, 0) != 0:
        print("[run_lua] prelude error: " + last_error())
        return 1

    rc = L.luaL_loadbuffer(S, source, len(source), chunkname.encode("utf-8"))
    if rc != 0:
        print("[run_lua] load error: " + last_error())
        return 1

    for a in extra:
        L.lua_pushstring(S, a.encode("utf-8"))

    rc = L.lua_pcall(S, len(extra), 0, 0)
    if rc != 0:
        print("[run_lua] runtime error: " + last_error())
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
