# Hook 瘦身与同空洞迁移验证

日期：2026-05-28

## 背景

`resident-slot` 版本已经验证 1x1/1x2 的命中与 fallback 分支，但 `02089190` 的 copy hook 使用了：

```text
COPY_HOOK_ADDR=0x02074140
LOAD_HOOK_ADDR=0x02074200
copy_hook_size=0xC0
```

这正好填满 `0x02074140..0x02074200`，无法继续直接追加多 slot、二分查找或 miss 调度逻辑。

## 本次方案

新增 probe：

```text
tools/patch_vram_font_chunk_table_slim_moved_probe.py
rom/test_vram_font_chunk_table_slim_moved_probe.nds
plan/cache/vram-font-bypass/chunk-table-slim-moved-samples.json
```

改动点：

- copy hook 只保留一个 `vars_base` literal，`map/chunk/current_char` 改为从固定偏移读取。
- load hook 从 `0x02074200` 后移到 `0x02074220`。
- overlay 的 `LOAD_PATCH_ADDR` 分支目标同步改到 `0x02074220`。
- payload 仍留在原 ARM9 主空洞内，没有迁到远端新洞。

静态布局：

```text
SAVE_CHAR_HOOK_ADDR = 0x0207411C
COPY_HOOK_ADDR      = 0x02074140
MOVED_LOAD_HOOK     = 0x02074220
PATCH_SIZE          = 0x2C0

copy_hook_size = 0xA0
copy_budget    = 0xE0
copy_margin    = 0x40
load_hook_size = 0x11C
payload_size   = 0x2C0
```

ROM 头信息检查：

```text
rom/test_vram_font_chunk_table_slim_moved_probe.nds
title=NARUTORPG3
code=ANTJ
Header CRC OK
Banner CRC OK
```

## 运行时样本

DeSmuME MCP 使用测试 ROM：

```text
rom/test_vram_font_chunk_table_slim_moved_probe.nds
breakpoint=0x020087BC
current_char_address=0x020743C0
```

关键样本：

```text
0x82CD, R2=0x40 -> R0=0x022831A0  1x2 resident hit
0x82DF, R2=0x40 -> R0=0x02283120  1x2 fallback
0x82A2, R2=0x40 -> R0=0x02283120  1x2 fallback
0x82BD, R2=0x20 -> R0=0x02283040  1x1 resident hit
```

## 结论

- copy hook 已从 `0xC0` 瘦到 `0xA0`。
- 同一主空洞内把 load hook 后移到 `0x02074220` 后，copy hook 获得 `0x40` 字节余量。
- resident/fallback 行为未被破坏，1x1 与 1x2 的关键路径仍能命中预期 RAM glyph。
- 这次迁移只是主空洞内部重排，不是完整代码区迁移；后续复杂逻辑仍应继续拆出 copy 热路径。

## 后续建议

下一步可以在 `0x40` 余量内验证极小的多 resident slot 或 miss flag，但真实缺页加载仍不应放进 `02089190` copy hook。更稳妥的方向是把 copy hook 保持为快速查表和状态记录，chunk 预扫/加载放到绘制热路径外。
