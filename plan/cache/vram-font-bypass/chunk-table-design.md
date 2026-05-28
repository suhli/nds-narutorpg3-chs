# 阶段缓存：chunk table 设计草案

更新时间：2026-05-28

## 背景

`chunk_id fallback` 原型已经验证：

```text
chunk_id == 0  -> resident glyph
chunk_id != 0  -> fallback glyph
```

下一步不能直接把 NitroFS 加载塞进 `02089190` copy hook。该 hook 处在逐字绘制热路径上，当前空洞空间也有限，更适合只做快速查表和 fallback 决策。

## 目标

把 `chunk_id` 从“非 0 即 fallback”升级为“查 resident chunk table 后决定是否命中”：

```text
entry.char_code -> entry.chunk_id + entry.glyph_offset
entry.chunk_id  -> resident slot / fallback
resident slot   -> chunk_base + glyph_offset
fallback        -> fallback_base + fallback_offset
```

本阶段先设计和验证 resident table，不做真实缺页加载。

## 文件格式草案

继续保留两套 map/chunk：

```text
font/chs_1x1.map
font/chs_1x1.chunk
font/chs_1x2.map
font/chs_1x2.chunk
```

新增 chunk table 可先做成内存结构，不急于落成独立 NitroFS 文件。后续需要静态描述时再加：

```text
font/chs_1x1.ctab
font/chs_1x2.ctab
```

建议静态 `CHTB` entry：

```text
u16 chunk_id
u16 glyph_size
u32 glyph_count
u32 chunk_file_offset_or_file_id
u32 packed_size
u32 unpacked_size
u32 flags
u32 reserved
```

如果后续把每个 chunk 拆成独立文件，`chunk_file_offset_or_file_id` 可解释为文件编号；如果合并成一个 chunk pack，则解释为 pack 内偏移。

## 运行时结构草案

先为 1x1 和 1x2 各保留一个 resident slot：

```text
resident_slot {
  u16 chunk_id
  u16 glyph_size
  u32 chunk_base
  u32 chunk_size
}
```

fallback 独立保存：

```text
fallback_slot {
  u32 glyph_base
  u32 glyph_size
}
```

最小 hook 逻辑：

```text
if entry.chunk_id == resident_slot.chunk_id and resident_slot.chunk_base != 0:
    R0 = resident_slot.chunk_base + entry.glyph_offset
else:
    R0 = fallback_slot.glyph_base
```

## 为什么先不做真实加载

- `02089190` 是逐字 copy hook，里面调用 NitroFS 读取会放大卡顿和重入风险。
- 当前 ARM9 空洞已经承载 save-char、copy-hook、load-hook、路径字符串和变量区，继续扩展复杂 loader 风险偏高。
- 真实加载需要确定 chunk 生命周期：何时换页、是否允许同步加载、是否预扫文本、失败后如何恢复。

因此下一次 runtime probe 应只验证 resident table 分支：

```text
chunk_id=0, resident_slot=0 -> resident glyph
chunk_id=1, resident_slot=0 -> fallback glyph
chunk_id=1, resident_slot=1 -> resident glyph
```

## 后续迁移方向

1. 单 resident slot 验证通过后，扩展为 2-4 个小型 resident slots。
2. map 查找从线性扫描迁移到按 `char_code` 排序后的二分查找。
3. chunk miss 不在 copy hook 内加载，只设置 miss 标记或走 fallback；加载由绘制前预扫或专门调度点完成。
4. chunk 数据可以从“独立 chunk 文件”或“chunk pack + offset”两条路线中选一种继续验证。

## 2026-05-28 resident-slot probe

新增：

```text
tools/patch_vram_font_chunk_table_probe.py
rom/test_vram_font_chunk_table_probe.nds
plan/cache/vram-font-bypass/chunk-table-samples.json
```

构建目录：

```text
rom/unpacked/vram_font_chunk_table_probe_v2
```

静态检查：

```text
copy_hook_size = 0xC0
COPY_HOOK_ADDR = 0x02074140
LOAD_HOOK_ADDR = 0x02074200
```

这说明 resident-slot 版本的 copy hook 已经正好用满 `0x02074140..0x02074200`，后续若继续增加逻辑，不能再直接塞进当前 copy hook 区间，必须移动 load hook、缩短逻辑或迁移到新代码区。

ROM 头信息检查通过：

```text
rom/test_vram_font_chunk_table_probe.nds
title=NARUTORPG3
code=ANTJ
Header CRC OK
Banner CRC OK
```

当前 probe 参数：

```text
resident_1x1_chunk_id = 0
resident_1x2_chunk_id = 1
fallback_offset       = 0x20
```

MCP 样本：

```text
0x82CD, R2=0x40 -> R0=0x022831A0  chunk_id=1, resident_1x2=1, resident hit
0x82DF, R2=0x40 -> R0=0x02283120  chunk_id=0, resident_1x2=1, fallback
0x82A2, R2=0x40 -> R0=0x02283120  chunk_id=0, resident_1x2=1, fallback
```

结论：
- `entry.chunk_id == resident_slot.chunk_id` 的 resident 命中路径已在 1x2 上验证。
- `entry.chunk_id != resident_slot.chunk_id` 的 fallback 路径已在 1x2 上验证。
- 首轮没有稳定复现到 1x1 的 `chunk_id=0/resident_slot=0` 正例，因此追加了专用 1x1 probe。

## 2026-05-28 1x1 resident-slot 补充验证

已扩展：

```text
tools/patch_vram_font_chunk_table_probe.py
```

新增可配置参数：

```text
--shared-1x1-chunk-id
--char-1x1-extra-chunk-id
--shared-1x2-chunk-id
--char-1x2-a-chunk-id
--char-1x2-b-chunk-id
```

新增专用 ROM：

```text
rom/test_vram_font_chunk_table_1x1_probe.nds
```

构建目录：

```text
rom/unpacked/vram_font_chunk_table_1x1_probe
```

构建参数：

```text
--char-1x1-extra-chunk-id 0
```

这会把稳定出现在 1x1 路径的 `0x82BD` 设置为 `chunk_id=0`，与 `resident_1x1_chunk_id=0` 匹配。

ROM 头信息检查通过：

```text
rom/test_vram_font_chunk_table_1x1_probe.nds
title=NARUTORPG3
code=ANTJ
Header CRC OK
Banner CRC OK
```

MCP 样本：

```text
0x82CD, R2=0x40 -> R0=0x022831A0  chunk_id=1, resident_1x2=1, resident hit
0x82DF, R2=0x40 -> R0=0x02283120  chunk_id=0, resident_1x2=1, fallback
0x82A2, R2=0x40 -> R0=0x02283120  chunk_id=0, resident_1x2=1, fallback
0x82BD, R2=0x20 -> R0=0x02283040  chunk_id=0, resident_1x1=0, resident hit
```

结论：
- 单 resident slot 的命中/未命中分支已覆盖 1x1 与 1x2。
- 当前 copy hook 仍然正好用满 `0x02074140..0x02074200`，下一步不应继续往这里追加复杂逻辑。
- 下一阶段可转向 hook 瘦身、移动代码区、多 resident slot，或先设计绘制热路径外的 chunk miss 调度。
