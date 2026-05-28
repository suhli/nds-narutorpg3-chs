# 阶段缓存：chunk_id fallback 原型

更新时间：2026-05-28

## 目标

在 formal v0 格式上验证 `chunk_id` 字段是否能参与运行时决策：

```text
chunk_id == 0  -> 当前 chunk 已驻留，使用 entry.glyph_offset
chunk_id != 0  -> 当前 chunk 未驻留，先退回 fallback glyph
```

本阶段只验证 fallback 行为，不做真实分页加载。

## 新增产物

```text
tools/patch_vram_font_chunk_fallback_probe.py
rom/test_vram_font_chunk_fallback_probe.nds
plan/cache/vram-font-bypass/chunk-fallback-samples.json
```

ROM 仍从 `rom/origin.nds` 解包后重新打包生成，没有覆盖原版 ROM。

## 文件结构

沿用 formal v0：

```text
font/chs_1x1.map
font/chs_1x1.chunk
font/chs_1x2.map
font/chs_1x2.chunk
```

静态文件大小：

```text
chs_1x1.map   0x40
chs_1x1.chunk 0x80
chs_1x2.map   0x50
chs_1x2.chunk 0xE0
```

map entry 仍是：

```text
u32 char_code
u32 glyph_offset
u16 advance
u16 flags
u16 chunk_id
u16 reserved
```

当前 probe 使用 `ldr r12, [entry + 0x0C]` 读取 `chunk_id/reserved` 的 32-bit 合并值。因为 `reserved=0`，该值可以直接用于判断 `chunk_id == 0`。

## 运行时 hook 行为

`02089190` 前的 copy hook 保持按 `R2` 分流：

```text
R2 == 0x20 -> chs_1x1.map + chs_1x1.chunk
R2 == 0x40 -> chs_1x2.map + chs_1x2.chunk
```

命中 entry 后：

```text
if chunk_id == 0:
    R0 = chunk_base + glyph_offset
else:
    R0 = chunk_base + 0x20
```

`0x20` 是当前 chunk header 大小，也作为每个 chunk 的 fallback glyph offset。

## MCP 验证

采样 ROM：

```text
D:\repos\nds-narutorpg3-chs\rom\test_vram_font_chunk_fallback_probe.nds
```

断点：

```text
0x020087BC
```

当前字符保存地址：

```text
0x020743C0
```

关键样本：

```text
0x82CD, R2=0x40 -> R0=0x02283120  fallback, chunk_id=1
0x82BD, R2=0x20 -> R0=0x02283000  fallback, chunk_id=1
0x82A2, R2=0x40 -> R0=0x02283160  resident, chunk_id=0
0x82A2, R2=0x20 -> R0=0x02283020  resident, chunk_id=0
0x82DF, R2=0x40 -> R0=0x022831A0  resident, chunk_id=0
```

最终采样状态：

```text
running=1 ARM9_PC=0x0208FF14 ARM7_PC=0x038042B0
```

## 结论

- `chunk_id` 字段可以在当前 hook 空间内参与分支。
- `chunk_id != 0` 不再自然落回原日文字形，而是可以稳定命中显式 fallback glyph。
- fallback glyph 放在 chunk header 后第一个 glyph 位置可行，offset 固定为 `0x20`。
- resident 与 fallback 可以共存于同一 formal v0 map/chunk 结构中。

## 下一步

正式分页方案应从这个原型继续推进：

```text
map 常驻
chunk table 常驻或小表常驻
chunk_id == resident_chunk -> 使用 glyph_offset
chunk_id != resident_chunk -> 尝试加载目标 chunk
加载失败或暂未实现 -> 使用 fallback glyph
```

查找策略仍需从线性查找迁移到排序表/二分查找；真实分页加载还需要补充 chunk table 文件格式、chunk 生命周期、staging buffer 和错误恢复策略。
