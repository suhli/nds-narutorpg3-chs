# 阶段缓存：DeSmuME MCP 更新验证

## 背景

用户说明 DeSmuME MCP 功能已经更新，需要启动 MCP 并同步更新项目 skill。

当前执行前已读取：

- `plan/state.yaml`
- `plan/vram-font-bypass.md`
- `plan/cache/vram-font-bypass/runtime-observation.md`
- `.codex/skills/desmume-mcp-workflow/SKILL.md`

## 验证环境

- DeSmuME：`tools/desmume.exe`
- 启动参数：`--mcp`
- MCP 地址：`http://127.0.0.1:8765/`
- ROM：`rom/origin.nds`，仅作为只读加载验证，未修改。

## tools/list 结果摘要

本次 `tools/list` 返回 19 个工具。相对旧 skill，新增或需要补充记录的工具为：

- `nds_screenshot`
- `nds_input_key`
- `nds_input_touch`
- `nds_input_release_all`

新增接口参数：

- `nds_screenshot`：可传 `screen: both|main|touch`，可传 `path` 保存 BMP。
- `nds_input_key`：`button` 为 DS 按键名，`pressed` 控制按下或释放。
- `nds_input_touch`：`x` 范围 0-255，`y` 范围 0-191，`touch` 控制按下或释放。
- `nds_input_release_all`：无参数，释放全部按键和触摸输入。

## 调用验证

临时启动 MCP 后加载 `rom/origin.nds`，调用结果：

- `nds_load_rom` 返回 `OK: loaded`。
- `nds_get_rom_info` 返回 `title=NARUTORPG3 code=ANTJ`。
- `nds_input_key` 可按下并释放 `A`。
- `nds_input_touch` 可在 `(128,96)` 触摸并释放。
- `nds_input_release_all` 返回 `OK: all keys released`。
- `nds_screenshot` 成功保存 `256x384` BMP。

截图证据：

- `plan/cache/vram-font-bypass/mcp-update-screenshot.bmp`
- 文件大小：`294966` 字节。

## 对当前阶段的影响

运行时观察阶段此前的阻塞点是“正文/菜单字体绘制断点需要输入推进或 MCP 输入能力”。新版 MCP 已提供按键、触摸和释放全部接口，可以继续通过输入推进到正文或菜单，再观察 `0208671C`、`0208913C`、`0208916C` 等候选绘制链路断点。

## 已更新产物

- `.codex/skills/desmume-mcp-workflow/SKILL.md`
