# 阶段缓存：动态字体正式格式 v0 设计与验证

更新时间：2026-05-28

## 目标

在 split-map 原型基础上，把临时格式升级为带 header 的正式 v0 文件结构：

```text
font/chs_1x1.map
font/chs_1x1.chunk
font/chs_1x2.map
font/chs_1x2.chunk
```

目标不是一次性完成最终中文字库，而是先固定可验证的二进制契约，让后续分页、压缩、宽度和 flags 都有明确扩展位置。

## 文件格式 v0

### map header

大小：`0x20` bytes。

```text
0x00  char[4] magic        "CHMP"
0x04  u16     version      1
0x06  u16     header_size  0x20
0x08  u16     glyph_size   0x20 for 1x1, 0x40 for 1x2
0x0A  u16     entry_size   0x10
0x0C  u32     entry_count
0x10  u32     flags        0 for now
0x14  u32     default_chunk_id
0x18  u32     reserved0
0x1C  u32     reserved1
```

### map entry

大小：`0x10` bytes。

```text
0x00  u32 char_code
0x04  u32 glyph_offset     offset from chunk file start
0x08  u16 advance          0 means use original width/path for now
0x0A  u16 flags            reserved for width/layout/fallback bits
0x0C  u16 chunk_id         0 for the resident chunk in current prototype
0x0E  u16 reserved
```

当前 hook 只读取：

```text
entry_count
char_code
glyph_offset
```

`advance/flags/chunk_id` 先作为格式契约保留，后续实现分页或宽度控制时再启用。

### chunk header

大小：`0x20` bytes。

```text
0x00  char[4] magic        "CHCK"
0x04  u16     version      1
0x06  u16     header_size  0x20
0x08  u16     glyph_size   0x20 for 1x1, 0x40 for 1x2
0x0A  u16     compression  0 = none
0x0C  u32     glyph_count
0x10  u32     data_size
0x14  u32     flags
0x18  u32     reserved0
0x1C  u32     reserved1
0x20  bytes   glyph data
```

`glyph_offset` 当前从 chunk 文件起点计算，因此第一个 glyph 的 offset 是 `0x20`，不是 `0x00`。

## 新增测试脚本和 ROM

新增脚本：

```text
tools/patch_vram_font_formal_format_probe.py
```

有效 ROM：

```text
rom/test_vram_font_formal_format_probe.nds
rom/unpacked/vram_font_formal_format_probe/
```

构建命令：

```text
.\.venv\Scripts\python.exe -B tools\patch_vram_font_formal_format_probe.py
```

`ndstool -i` 可正常读取 ROM：

```text
Game title: NARUTORPG3
Game code: ANTJ
Header CRC: OK
Banner CRC: OK
```

生成文件大小：

```text
chs_1x1.map    0x40
chs_1x1.chunk  0x60
chs_1x2.map    0x50
chs_1x2.chunk  0xE0
```

静态 header 检查：

```text
chs_1x1.map   magic=CHMP version=1 header_size=0x20
chs_1x1.chunk magic=CHCK version=1 header_size=0x20
chs_1x2.map   magic=CHMP version=1 header_size=0x20
chs_1x2.chunk magic=CHCK version=1 header_size=0x20
```

## Hook 行为

`02089190` copy hook 仍使用 `R2` 分流：

```text
R2 == 0x20 -> 1x1 map/chunk
R2 == 0x40 -> 1x2 map/chunk
other      -> keep original R0
```

当前 header-aware 查表逻辑：

```text
entry_count = *(map + 0x0C)
entry       = map + 0x20

for i in range(entry_count):
    if entry.char_code == current_char:
        R0 = chunk + entry.glyph_offset
        break
    entry += 0x10
```

暂未在 ARM9 hook 中检查 magic/version，原因是当前 hook 空洞空间有限；magic/version 已由构建和静态验证保证。正式实现如果迁移到更充足的代码区，应补运行时格式检查和失败 fallback。

## MCP 验证

采样命令：

```text
.\.venv\Scripts\python.exe -B tools\sample_vram_font_chars_mcp.py --rom rom\test_vram_font_formal_format_probe.nds --current-char-address 020743C0 --max-samples 180 --seconds 24 --output plan\cache\vram-font-bypass\formal-format-samples.json
```

运行时加载指针区：

```text
020743A0:
02282F80 00000040 02282FE0 00000060
02283060 00000050 022830E0 000000E0
00008140
```

含义：

```text
1x1 map   -> 0x02282F80 size 0x40
1x1 chunk -> 0x02282FE0 size 0x60
1x2 map   -> 0x02283060 size 0x50
1x2 chunk -> 0x022830E0 size 0xE0
```

关键采样：

```text
0x82A2, R2=0x40 -> R0=0x02283100  (1x2 chunk + 0x20)
0x82CD, R2=0x40 -> R0=0x02283140  (1x2 chunk + 0x60)
0x82DF, R2=0x40 -> R0=0x02283180  (1x2 chunk + 0xA0)

0x82A2, R2=0x20 -> R0=0x02283000  (1x1 chunk + 0x20)
0x82BD, R2=0x20 -> R0=0x02283020  (1x1 chunk + 0x40)
```

收尾状态：

```text
running=1 ARM9_PC=0x0208FF18 ARM7_PC=0x038042B0
```

## 结论

已验证：

- 带 `CHMP/CHCK` header 的 formal v0 文件可以被加入 NitroFS 并预加载到 RAM。
- header-aware copy hook 可以读取 `entry_count`、跳过 `0x20` header、按 `0x10` entry 查找 glyph。
- `glyph_offset` 从 chunk 文件起点计算可行，第一枚 glyph 使用 offset `0x20`。
- 1x1/1x2 继续可用 `R2=0x20/0x40` 分流，同一个 `0x82A2` 仍能命中不同 chunk。

## 分页/分块设计草案

下一阶段不要把所有 glyph 数据做成单个常驻 chunk。建议 v0 后续扩展为：

```text
resident:
  chs_1x1.map
  chs_1x2.map
  small active chunk table

paged:
  chs_1x1_000.chunk
  chs_1x1_001.chunk
  chs_1x2_000.chunk
  chs_1x2_001.chunk
```

map entry 中的 `chunk_id` 指向当前或可加载的 chunk。早期实现可以先支持：

```text
chunk_id == 0 -> resident chunk
chunk_id != 0 -> fallback to original glyph or missing glyph
```

等文本页/场景预扫描能力明确后，再把 `chunk_id != 0` 接到按页加载或小型 RAM staging buffer。

## 下一步

- 决定正式 chunk 命名和 chunk table 结构。
- 设计缺字 fallback glyph，避免中文字符 miss 后误回原日文字形。
- 评估 map 是否需要排序并改成二分查找；当前线性查找只适合小规模验证。
