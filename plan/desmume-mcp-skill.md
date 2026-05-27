# 制作 DeSmuME MCP 调试 Skill

## 背景

仓库内的 `tools/desmume.exe` 是经过修改的 DeSmuME，可通过 `tools/desmume.exe --mcp` 从命令行启动模拟器并开启 MCP 服务。这个 MCP 用于 NDS ROM 调试，可在汉化过程中读取状态、加载 ROM、查看寄存器、读写内存和设置断点。

## 必要上下文

- DeSmuME MCP 是 HTTP JSON-RPC 服务，不是 stdio。
- 启动命令：`tools/desmume.exe --mcp`。
- HTTP 地址：`http://127.0.0.1:8765/`。
- 请求方式：HTTP `POST /`。
- 已验证 `tools/list` 能返回工具清单。
- 已验证 `tools/call` 调用 `nds_get_state` 成功。
- 模拟器验证应优先加载新打包 ROM 或任务专用测试 ROM；`rom/origin.nds` 只作为原版参考。

## 目标

- 创建项目 skill：`.claude/skills/desmume-mcp-workflow/SKILL.md`。
- 写明启动模拟器和 MCP 的方式。
- 写明 HTTP JSON-RPC 调用格式。
- 写明 DeSmuME MCP 提供的工具功能。
- 提供辅助脚本列出工具和调用工具。

## 阶段

### 1. 检查已有计划

状态：已完成。

`plan/` 中此前没有 DeSmuME MCP 相关计划。

### 2. 检查工具文件

状态：已完成。

已确认 `tools/desmume.exe` 存在，`--help` 显示支持 `--mcp`。

### 3. 确认 MCP 形态

状态：已完成。

用户确认该 MCP 是 HTTP 服务。随后通过本地启动确认监听地址为 `127.0.0.1:8765`。

### 4. 枚举 MCP 工具

状态：已完成。

通过 HTTP JSON-RPC `tools/list` 获取到工具清单。

### 5. 编写 skill 和辅助脚本

状态：已完成。

产物：

- `.claude/skills/desmume-mcp-workflow/SKILL.md`
- `.claude/skills/desmume-mcp-workflow/scripts/list_mcp_tools.py`
- `.claude/skills/desmume-mcp-workflow/scripts/call_mcp_tool.py`

### 6. 验证

状态：已完成。

- `list_mcp_tools.py --start` 可启动临时 MCP 并列出工具。
- `call_mcp_tool.py --tool nds_get_state --arguments '{}'` 可通过 HTTP MCP 返回运行状态。
- 收尾检查时没有残留 `desmume.exe` 进程。

## MCP 工具清单

执行控制：

- `nds_pause`
- `nds_resume`
- `nds_step`
- `nds_reset`
- `nds_get_state`

ROM 控制：

- `nds_load_rom`
- `nds_reload_rom`
- `nds_get_rom_info`

内存和寄存器：

- `nds_read_memory`
- `nds_write_memory`
- `nds_get_registers`

断点：

- `nds_set_breakpoint`
- `nds_clear_breakpoint`
- `nds_clear_all_breakpoints`
- `nds_list_breakpoints`

## 决策

- 使用仓库内 `tools/desmume.exe`。
- 使用 `tools/desmume.exe --mcp` 启动 HTTP MCP server。
- HTTP MCP 地址为 `http://127.0.0.1:8765/`。
- 使用 JSON-RPC POST 调用 `tools/list` 和 `tools/call`。
- 不使用 `rom/origin.nds` 作为修改输出；模拟器验证优先加载新打包 ROM 或临时测试 ROM。

## 后续

后续需要模拟器验证或运行时调试时，先读 `.claude/skills/desmume-mcp-workflow/SKILL.md`，再按当前任务新建或延续对应计划。
