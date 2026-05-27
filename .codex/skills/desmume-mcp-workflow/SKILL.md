---
name: desmume-mcp-workflow
description: Use this project skill when launching tools/desmume.exe with --mcp, connecting to its HTTP MCP server, loading an NDS ROM for emulator verification, or using DeSmuME MCP tools for memory/register/breakpoint debugging.
---

# DeSmuME MCP Workflow

## Core Facts

- Use the repository-local emulator at `tools/desmume.exe`.
- Start MCP mode with `tools/desmume.exe --mcp`.
- MCP is HTTP JSON-RPC, not stdio. The server listens on `http://127.0.0.1:8765/`.
- Send JSON-RPC requests with HTTP `POST /` and `Content-Type: application/json`.
- Prefer loading rebuilt/test ROMs. Treat `rom/origin.nds` as immutable reference material.
- Record emulator validation commands, loaded ROM path, breakpoints, and findings in `plan/`; write reverse-engineering discoveries to `hack/`.

## Start Emulator And MCP

For an interactive emulator window:

```powershell
.\tools\desmume.exe --mcp
```

For a hidden temporary server used only to list MCP tools:

```powershell
.\.venv\Scripts\python.exe .codex\skills\desmume-mcp-workflow\scripts\list_mcp_tools.py --start
```

If DeSmuME is already running in MCP mode, list tools from the existing server:

```powershell
.\.venv\Scripts\python.exe .codex\skills\desmume-mcp-workflow\scripts\list_mcp_tools.py
```

## HTTP JSON-RPC Shape

List tools:

```json
{"jsonrpc":"2.0","id":1,"method":"tools/list"}
```

Call a tool:

```json
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"nds_get_state","arguments":{}}}
```

Use the bundled helper for tool calls:

```powershell
.\.venv\Scripts\python.exe .codex\skills\desmume-mcp-workflow\scripts\call_mcp_tool.py --tool nds_get_state --arguments '{}'
```

Load a ROM through MCP. Prefer rebuilt ROMs such as `rom/narutorpg3_chs.nds` or task-specific test ROMs:

```powershell
.\.venv\Scripts\python.exe .codex\skills\desmume-mcp-workflow\scripts\call_mcp_tool.py --tool nds_load_rom --arguments '{"path":"D:\\repos\\nds-narutorpg3-chs\\rom\\narutorpg3_chs.nds"}'
```

## MCP Tools

### Execution Control

- `nds_pause`: Pause NDS emulation and break into debugger.
- `nds_resume`: Resume NDS emulation.
- `nds_step`: Single-step one instruction on both CPUs.
- `nds_reset`: Reset the NDS console.
- `nds_get_state`: Return running state, ARM9 PC, ARM7 PC, and ROM state.

### ROM Control

- `nds_load_rom`: Load a ROM file. Arguments: `path`.
- `nds_reload_rom`: Reload the last loaded ROM path.
- `nds_get_rom_info`: Return loaded ROM title and game code.

### Memory And Registers

- `nds_read_memory`: Read NDS memory. Arguments: `proc`, `address`, `size`.
- `nds_write_memory`: Write bytes to NDS memory. Arguments: `proc`, `address`, `value`.
- `nds_get_registers`: Get ARM registers for one CPU. Arguments: `proc`.

CPU selector:

- `proc: 0` means ARM9.
- `proc: 1` means ARM7.

Address and value conventions:

- `address` is a hex string such as `"02086870"` or `"0x02086870"`.
- `size` is an integer byte count.
- `value` is an even-length hex byte string such as `"AABBCCDD"`.

Examples:

```powershell
.\.venv\Scripts\python.exe .codex\skills\desmume-mcp-workflow\scripts\call_mcp_tool.py --tool nds_get_registers --arguments '{"proc":0}'
.\.venv\Scripts\python.exe .codex\skills\desmume-mcp-workflow\scripts\call_mcp_tool.py --tool nds_read_memory --arguments '{"proc":0,"address":"02086870","size":32}'
```

### Breakpoints

- `nds_set_breakpoint`: Set a breakpoint. Arguments: `type`, `address`, optional `proc` for execute breakpoints.
- `nds_clear_breakpoint`: Clear one breakpoint. Arguments match `nds_set_breakpoint`.
- `nds_clear_all_breakpoints`: Clear all execute/read/write breakpoints.
- `nds_list_breakpoints`: List execute ARM9/ARM7, read, and write breakpoints.

Breakpoint type values:

- `execute`
- `read`
- `write`

Examples:

```powershell
.\.venv\Scripts\python.exe .codex\skills\desmume-mcp-workflow\scripts\call_mcp_tool.py --tool nds_set_breakpoint --arguments '{"type":"execute","proc":0,"address":"02086870"}'
.\.venv\Scripts\python.exe .codex\skills\desmume-mcp-workflow\scripts\call_mcp_tool.py --tool nds_list_breakpoints --arguments '{}'
```

## Debugging Workflow

1. Check `plan/` for an existing debugging or verification plan.
2. Start `tools/desmume.exe --mcp`.
3. Load the rebuilt/test ROM through `nds_load_rom`.
4. Use `nds_get_state` and `nds_get_rom_info` to confirm the emulator state.
5. Set breakpoints before running risky checks.
6. Use `nds_pause`, `nds_step`, `nds_get_registers`, and `nds_read_memory` to inspect behavior.
7. Use `nds_write_memory` only for temporary emulator-memory experiments; do not treat it as ROM patching.
8. Record addresses, observations, breakpoint results, and next steps in the active `plan/` file.
