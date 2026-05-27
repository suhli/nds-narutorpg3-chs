# 阶段缓存：运行时字符序列采样

更新时间：2026-05-27

## 目标

为多字符小表验证寻找稳定出现的字符，并把 MCP 断点采样流程做成可复现工具。

## 新增工具

```text
tools/sample_vram_font_chars_mcp.py
```

功能：

- 通过 HTTP JSON-RPC 连接 DeSmuME MCP。
- 加载指定 ROM。
- 在 `020087BC` 设置 ARM9 execute breakpoint。
- 按输入计划推进标题/文本路径。
- 每次命中时记录 `current_char`、`R0`、`R1`、`R2`、`LR`。
- 清理断点并自动恢复可 resume 的调试暂停态。

默认输入计划：

```text
start@1.0,A@2.0,A@3.0,A@4.0,A@5.0,A@6.0
```

## no-op ROM 采样

命令：

```text
.\.venv\Scripts\python.exe -B tools\sample_vram_font_chars_mcp.py --rom rom\test_vram_font_copy_noop_probe.nds --current-char-address 020741C0 --stop-after-chars 0x82CD,0x82DF --max-samples 30 --output plan\cache\vram-font-bypass\runtime-char-samples.json
```

输出：

```text
plan/cache/vram-font-bypass/runtime-char-samples.json
```

关键序列：

```text
index 0  char=0x8140  R0=0x06881C00
index 1  char=0x8140  R0=0x06881C00
index 2  char=0x8140  R0=0x06881C00
index 3  char=0x8140  R0=0x06881C00
index 4  char=0x82CD  R0=0x06882280
index 5  char=0x82B6  R0=0x06882B80
index 6  char=0x82DF  R0=0x06882480
```

结论：`0x82CD` 和 `0x82DF` 在当前输入路径中稳定出现，可用于双项小表验证。

## 双字符 ROM 验证

命令：

```text
.\.venv\Scripts\python.exe -B tools\sample_vram_font_chars_mcp.py --rom rom\test_vram_font_multi_char_hook_probe.nds --current-char-address 02074480 --stop-after-chars 0x82CD,0x82DF --max-samples 30 --output plan\cache\vram-font-bypass\multi-char-verify-samples.json
```

输出：

```text
plan/cache/vram-font-bypass/multi-char-verify-samples.json
```

关键命中：

```text
index 4  char=0x82CD  R0=0x020741A0  R1=0x02292B40
index 6  char=0x82DF  R0=0x020741E0  R1=0x02292BC0
```

结论：两项小表的两个分支均已运行时验证。

## 后续入口

下一步可以把 `02074140` 的硬编码双比较改为表驱动循环：

```text
for entry in glyph_map:
    if entry.char_code == current_char:
        R0 = entry.glyph_addr
        break
```

短期表仍放 ARM9 空洞；验证通过后再迁移到预加载的普通 RAM 映射表。
