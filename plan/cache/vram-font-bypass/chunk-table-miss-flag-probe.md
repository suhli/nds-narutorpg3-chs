# Chunk miss flag 原型验证

日期：2026-05-28

## 背景

上一轮 hook 瘦身与同空洞迁移后，copy hook 区间预算变为：

```text
copy hook: 0x02074140
load hook: 0x02074220
copy_budget = 0xE0
```

本轮不在逐字 copy hook 中做 NitroFS 缺页加载，只验证一个最小 miss 状态记录：当 map 命中但 `entry.chunk_id != resident_slot.chunk_id` 时，继续返回 fallback glyph，同时把 miss 信息写入变量区，供后续热路径外 loader 或预扫逻辑读取。

## 新增文件

```text
tools/patch_vram_font_chunk_table_miss_flag_probe.py
rom/test_vram_font_chunk_table_miss_flag_probe.nds
plan/cache/vram-font-bypass/chunk-table-miss-flag-samples.json
```

`tools/sample_vram_font_chars_mcp.py` 增加了 `--extra-read` 参数，用于在每个 breakpoint 样本里同步读取额外内存块。本次使用：

```text
--extra-read miss=020743C4:16
```

## miss 变量布局

```text
0x020743C4  miss_flag
0x020743C8  miss_char
0x020743CC  miss_chunk_id
0x020743D0  miss_mode
```

copy hook 入口清 `miss_flag=0`。发生 resident slot 不匹配时写入：

```text
miss_flag     = 1
miss_char     = current_char
miss_chunk_id = entry.chunk_id
miss_mode     = R2
```

注意：当前只清 `miss_flag`，其余字段可能保留上一次 miss 的值。读取方必须以 `miss_flag==1` 判断这组字段是否有效。

## 静态结果

```text
copy_hook_size = 0xC0
copy_budget    = 0xE0
copy_margin    = 0x20
load_hook_addr = 0x02074220
load_hook_size = 0x11C
```

ROM 头信息检查：

```text
rom/test_vram_font_chunk_table_miss_flag_probe.nds
title=NARUTORPG3
code=ANTJ
Header CRC OK
Banner CRC OK
```

## MCP 验证

采样命令：

```text
.\.venv\Scripts\python.exe -B tools\sample_vram_font_chars_mcp.py --rom rom\test_vram_font_chunk_table_miss_flag_probe.nds --current-char-address 020743C0 --extra-read miss=020743C4:16 --stop-after-chars 0x82CD,0x82DF,0x82BD --max-samples 140 --seconds 40 --output plan\cache\vram-font-bypass\chunk-table-miss-flag-samples.json
```

关键样本：

```text
0x82CD, R2=0x40 -> R0=0x022831A0, miss=00000000 00000000 00000000 00000000
0x82DF, R2=0x40 -> R0=0x02283120, miss=00000001 000082DF 00000000 00000040
0x82A2, R2=0x40 -> R0=0x02283120, miss=00000001 000082A2 00000000 00000040
0x82BD, R2=0x20 -> R0=0x02283040, miss=00000000 000082A2 00000000 00000040
```

解释：

- `0x82DF` 和 `0x82A2` 在 1x2 路径中 `chunk_id=0`，但当前 `resident_1x2_chunk_id=1`，因此记录 miss 并返回 fallback glyph。
- `0x82CD` 是 1x2 resident hit，`miss_flag=0`。
- `0x82BD` 是 1x1 resident hit，`miss_flag=0`；后续字段保留旧值但无效。

## 结论

- copy hook 可以在现有同空洞迁移布局内记录最小 miss 状态。
- 记录 miss 后，resident/fallback 的 R0 行为保持不变。
- 该版本已用掉 slim/moved 后释放出的部分余量，copy hook 从 `0xA0` 增至 `0xC0`，仍在 `0xE0` budget 内。
- 后续更适合先设计热路径外的 miss 消费/预扫加载，而不是继续把 loader 塞进 copy hook。
