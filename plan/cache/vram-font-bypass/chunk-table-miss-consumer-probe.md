# Chunk miss consumer 原型验证

日期：2026-05-28

## 背景

`chunk-table-miss-flag-probe` 已经证明 copy hook 可以在 resident slot 不匹配时记录：

```text
miss_flag / miss_char / miss_chunk_id / miss_mode
```

本次继续验证下一步：在逐字 copy hook 外消费上一轮 miss，更新 resident slot id。当前仍不做 NitroFS 同步读取，也不搬运真实 chunk 数据，只验证调度位置和状态接口。

## 新增文件

```text
tools/patch_vram_font_chunk_table_miss_consumer_probe.py
rom/test_vram_font_chunk_table_miss_consumer_probe.nds
plan/cache/vram-font-bypass/chunk-table-miss-consumer-samples.json
```

## Hook 布局

沿用主变量区：

```text
0x020743C4  miss_flag
0x020743C8  miss_char
0x020743CC  miss_chunk_id
0x020743D0  miss_mode
0x020743D4  resident_1x1_chunk_id
0x020743D8  resident_1x2_chunk_id
```

新增消费 hook：

```text
patch point    = 0x0208913C
consume hook   = 0x02073D64
consume size   = 0x50
```

`0x0208913C` 是已验证绘制链路入口。consumer 在原函数 prologue 处运行：

```text
if miss_flag == 1:
    if miss_mode == 0x20:
        resident_1x1_chunk_id = miss_chunk_id
    if miss_mode == 0x40:
        resident_1x2_chunk_id = miss_chunk_id
    miss_flag = 0
```

copy hook 同时改为从变量区读取 resident slot id，而不是 hardcode：

```text
R2=0x20 -> resident_1x1_chunk_id
R2=0x40 -> resident_1x2_chunk_id
```

## 静态结果

```text
copy_hook_size = 0xC0
copy_budget    = 0xE0
consume_hook   = 0x02073D64 size=0x50
load_hook      = 0x02074220 size=0x11C
vars_end       = 0x020743DC
```

ROM 头信息检查：

```text
rom/test_vram_font_chunk_table_miss_consumer_probe.nds
title=NARUTORPG3
code=ANTJ
Header CRC OK
Banner CRC OK
```

## MCP 验证

采样命令：

```text
.\.venv\Scripts\python.exe -B tools\sample_vram_font_chars_mcp.py --rom rom\test_vram_font_chunk_table_miss_consumer_probe.nds --current-char-address 020743C0 --extra-read state=020743C4:24 --stop-after-chars 0x82CD,0x82DF,0x82A2,0x82BD --max-samples 150 --seconds 45 --output plan\cache\vram-font-bypass\chunk-table-miss-consumer-samples.json
```

关键样本：

```text
0x82CD, R2=0x40 -> R0=0x022831A0, state=00000000 00000000 00000000 00000000 00000000 00000001
0x82DF, R2=0x40 -> R0=0x02283120, state=00000001 000082DF 00000000 00000040 00000000 00000001
0x82A9, R2=0x40 -> R0=0x06881D80, state=00000000 000082DF 00000000 00000040 00000000 00000000
0x82A2, R2=0x40 -> R0=0x02283160, state=00000000 000082DF 00000000 00000040 00000000 00000000
```

字段解释：

```text
state words = miss_flag, miss_char, miss_chunk_id, miss_mode, resident_1x1, resident_1x2
```

关键变化：

- 初始 `resident_1x2_chunk_id=1`，因此 `0x82CD/chunk_id=1` 命中 resident。
- `0x82DF/chunk_id=0` 首次出现时，仍因 `resident_1x2=1` 走 fallback，并记录 miss。
- 下一次进入 `0x0208913C` 时 consumer 消费该 miss，把 `resident_1x2_chunk_id` 更新为 `0` 并清 `miss_flag`。
- 后续 `0x82A2/chunk_id=0` 已不再 fallback，而是命中 resident glyph `0x02283160`。

## 结论

- `0x0208913C` 可以作为逐字 copy hook 之外的 miss 消费点。
- miss 生产和消费的最小状态接口成立：copy hook 只记录 miss，高一层入口消费 miss 并更新 resident slot。
- 当前只验证 resident slot id 翻转，没有实现真实 chunk 数据换页；正式 loader 仍需要在消费点附近或文本块切换点补实际加载/搬运。
- 单 slot 翻转会让旧 resident chunk 失效，例如 `resident_1x2` 从 `1` 切到 `0` 后，`chunk_id=1` 的字符会重新 fallback。这是单 slot 原型的预期限制。
