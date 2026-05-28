# Chunk resident copy 原型验证

日期：2026-05-28

## 背景

`chunk-table-miss-consumer-probe` 已确认 `0x0208913C` 可以在逐字 copy hook 外消费上一轮 miss，并更新 resident slot id。下一步需要验证 consumer 不只是改 slot id，而是能把目标 chunk page 搬到当前 resident page，让后续 copy hook 读到真实换入后的 glyph 数据。

## 新增文件

```text
tools/patch_vram_font_chunk_table_resident_copy_probe.py
rom/test_vram_font_chunk_table_resident_copy_probe.nds
rom/test_vram_font_chunk_table_resident_copy_v2_probe.nds
plan/cache/vram-font-bypass/chunk-table-resident-copy-samples.json
plan/cache/vram-font-bypass/chunk-table-resident-copy-v2-samples.json
```

## v1 结果

v1 把 resident buffer 放在固定 ARM9 空洞 `0x0207A668` 附近，consumer miss 后把目标页拷进去。MCP 样本显示 consumer 确实会写入目标页，但进入文本前该区域已经出现运行时数据：

```text
0x0207A6C8 -> 0216C5A0 00000000
0x0207A708 -> 00000000 00000000
```

结论：固定 ARM9 空洞不适合作为长期 resident buffer。即使静态看是空洞，运行时也可能被别的系统复用。

## v2 布局

v2 把 resident page 放回 `chs_1x2.chunk` 的 heap buffer 内，避免依赖固定 ARM9 RAM：

```text
chs_1x2.chunk:
  0x000  CHPK header
  0x020  resident page
  0x100  source page 0
  0x1E0  source page 1
total size = 0x2C0
```

1x2 copy hook 命中路径固定从 `1x2_chunk_ptr + 0x20` 读取 resident page；consumer 在 miss 时把 `source page 0/1` 拷贝到 `resident page`，再更新 `resident_1x2_chunk_id`。

关键 hook 与变量：

```text
0x0208913C -> 0x02073D64
copy_hook_size    = 0xCC
copy_budget       = 0xE0
consume_hook_size = 0x90
load_hook         = 0x02074220 size=0x11C

0x020743C4  miss_flag
0x020743C8  miss_char
0x020743CC  miss_chunk_id
0x020743D0  miss_mode
0x020743D4  resident_1x1_chunk_id
0x020743D8  resident_1x2_chunk_id
```

ROM 检查：

```text
rom/test_vram_font_chunk_table_resident_copy_v2_probe.nds
title=NARUTORPG3
code=ANTJ
Header CRC OK
Banner CRC OK
```

## MCP 验证

采样命令：

```text
.\.venv\Scripts\python.exe -B tools\sample_vram_font_chars_mcp.py --rom rom\test_vram_font_chunk_table_resident_copy_v2_probe.nds --current-char-address 020743C0 --extra-read state=020743C4:24,ptrs=020743A0:32 --read-r0-size 8 --stop-after-chars 0x82CD,0x82DF,0x82A2,0x82BD --max-samples 150 --seconds 45 --output plan\cache\vram-font-bypass\chunk-table-resident-copy-v2-samples.json
```

运行时指针：

```text
1x1_map_ptr   = 0x02282F80 size=0x40
1x1_chunk_ptr = 0x02282FE0 size=0x80
1x2_map_ptr   = 0x02283080 size=0x50
1x2_chunk_ptr = 0x02283100 size=0x2C0
resident page = 0x02283120
```

关键样本：

```text
idx 4   0x82CD/R2=0x40 -> R0=0x022831C0, R0 data=95599559 95599559, state=... resident_1x2=1
idx 6   0x82DF/R2=0x40 -> R0=0x02283140, R0 data=C77CC77C C77CC77C, miss=1/82DF/0/0x40, resident_1x2=1
idx 7   next entry      -> miss_flag=0, resident_1x2=0
idx 18  0x82A2/R2=0x40 -> R0=0x02283180, R0 data=73377337 73377337, resident_1x2=0
idx 85  0x82CD/R2=0x40 -> R0=0x02283140, R0 data=B66BB66B B66BB66B, miss=1/82CD/1/0x40, resident_1x2=0
idx 87  0x82A2/R2=0x40 -> R0=0x02283180, R0 data=73377337 73377337, resident_1x2=0
idx 114 0x82BD/R2=0x20 -> R0=0x02283040, R0 data=62266226 62266226
```

字段解释：

```text
state words = miss_flag, miss_char, miss_chunk_id, miss_mode, resident_1x1, resident_1x2
```

验证判断：

- v2 已证明 consumer 可以在 `0x0208913C` 层把目标 1x2 page 拷入 heap 内 resident page。
- `82DF` 首次 miss 后，下一轮 consumer 把 `resident_1x2` 从 `1` 切到 `0`，后续 `82A2` 命中 page0 图样 `73377337`，不是旧的 page1 图样。
- 1x1 路径未受影响，`82BD/R2=0x20` 仍命中 `0x02283040`。
- 单 1x2 resident slot 会抖动：当 resident 已切到 page0 后，`82CD/chunk_id=1` 会重新 miss 并用 page0 fallback 图样 `B66BB66B`。

## 结论

resident buffer 应放在已加载 chunk 的 heap buffer 内，而不是固定 ARM9 空洞。当前最小动态换页链路已经成立：

```text
copy hook records miss -> 0x0208913C consumer copies target page -> copy hook reads resident page
```

下一步不应继续扩大逐字 copy hook，而应验证更接近正式方案的缓存策略：至少 2 个 1x2 resident slot，或在文本块入口预扫本轮所需 chunk，减少单 slot 在 chunk 0/1 之间反复失效。

## 验证记录

```text
ndstool -i rom/test_vram_font_chunk_table_resident_copy_v2_probe.nds
  title=NARUTORPG3 code=ANTJ
  Header CRC OK
  Banner CRC OK

syntax compile without pyc:
  tools/sample_vram_font_chars_mcp.py OK
  tools/patch_vram_font_chunk_table_resident_copy_probe.py OK
```

常规 `py_compile` 因 `tools/__pycache__` 写入权限返回 `WinError 5`，已改用只读 `compile(...)` 做语法检查。
