# 阶段缓存：动态 glyph 缓存正式设计

更新时间：2026-05-27

## 当前结论

当前最可行路线是方案 A：动态 glyph 缓存。

已确认的基础能力：

- `0208913C -> 0208916C -> 0208671C -> 02089170 -> 02089190` 是实际绘制链路。
- `0208914C` 可以保存当前字符码。
- `02089190` 前可以按字符码替换 `R0=glyph_source`。
- 原复制函数 `020087BC` 可以从 ARM9 RAM 读取 glyph 数据，不要求源地址必须是原 VRAM 字库区。
- overlay 尾部追加 hook 会踩 overlay_0000 BSS，不能再使用；当前 ARM9 空洞 hook 可用。

## 目标

把“单字符测试替换”扩展为可服务中文显示的最小动态缓存：

```text
text char code -> lookup custom glyph -> prepare glyph bytes -> R0 points to prepared glyph -> 020087BC copies to render buffer
```

该阶段只做机制设计和最小原型，不进入大规模文本 dump 和翻译。

## 设计草案

### 1. 字符识别

短期仍沿用 `0208914C` 保存当前字符码：

```text
CURRENT_CHAR_ADDR = 0x020741C0
```

正式实现时可以继续在 `02089190` 前读取该值，也可以迁移到 `0208671C` 处统一处理字符码到 glyph 的映射。

### 2. glyph 数据来源

候选优先级：

1. NitroFS 新增文件，例如 `data/font/chs_1x2.chr` 和 `data/font/chs_map.bin`。
2. ARM9 扩展区或明确空洞，只用于小型测试，不适合作为最终全量中文 glyph 仓库。
3. 独立 overlay，适合放代码，不适合直接放大量字模数据。

推荐先用 NitroFS 新文件做正式数据来源，因为它不挤占 VRAM，也不会扩大 overlay BSS 风险。

### 3. 映射结构

最小映射项：

```text
u16 char_code
u16 flags_or_width
u32 glyph_offset
```

其中 `glyph_offset` 指向中文 glyph 文件内偏移。1x1 和 1x2 可以先拆成两个 map，避免早期把 mode 逻辑混在一起。

### 4. 缓存槽

初版可以先做“单槽 RAM glyph 缓存”：

```text
CUSTOM_GLYPH_ADDR = 0x02074180
```

命中中文字符时，把 glyph 读入或复制到该地址，再把 `R0` 改成 `CUSTOM_GLYPH_ADDR`。

单槽方案适合验证，但正式显示同屏多字时需要扩展为多槽：

```text
slot {
  u16 char_code
  u16 mode
  u32 glyph_addr
  u32 last_used
}
```

### 5. 关键风险

- `02074180` 目前只是测试地址，容量很小，不能承载多槽缓存。
- 需要确认能否在绘制路径中同步读取 NitroFS；如果不能，需要提前把中文 glyph 文件加载到普通 RAM。
- 需要确认 1x1 字体路径是否复用同一 copy 逻辑。
- 需要确认字宽、换行和菜单布局是否只依赖 `.tbl`，还是另有宽度表。

## 下一步实验

1. 构建一个“两个字符映射到两个 RAM glyph”的测试 ROM。
2. 将 `match-char` 从单值扩展为小表查找，例如 `0x82CD`、`0x82DF`。
3. 先不接 NitroFS 文件读取，只把两个 glyph 放在 ARM9 空洞，证明多字符选择逻辑。
4. 通过 DeSmuME MCP 验证两个不同字符都能在 `020087BC` 前把 `R0` 替换到不同 glyph 地址。

## 2026-05-27 多字符 probe 进展

已新增：

```text
tools/patch_vram_font_multi_char_hook_probe.py
rom/test_vram_font_multi_char_hook_probe.nds
rom/test_vram_font_multi_char_8140_probe.nds
```

默认 `0x82CD/0x82DF` 版本已完成构建和运行时验证。此前先用 `0x8140 -> 0x020741A0` 验证了第一项：

```text
020087BC:
current_char=00008140
R0=0x020741A0
R1=0x02292A40
```

随后通过 `tools/sample_vram_font_chars_mcp.py` 采样确认 `0x82CD/0x82DF` 在当前路径稳定出现，并完成默认双字符 ROM 验证：

```text
0x82CD -> R0=0x020741A0
0x82DF -> R0=0x020741E0
```

结论：两项小表 hook 的两个分支均成立。

## 2026-05-27 表驱动原型

已新增：

```text
tools/patch_vram_font_table_hook_probe.py
rom/test_vram_font_table_hook_probe.nds
```

`02074140` 已从硬编码双比较改为遍历表：

```text
lookup_table:
0x82CD -> 0x02074200
0x82DF -> 0x02074240
```

MCP 验证：

```text
0x82CD -> R0=0x02074200
0x82DF -> R0=0x02074240
```

详细记录见 `plan/cache/vram-font-bypass/table-lookup-probe.md`。

下一步进入 glyph 数据来源设计：先把中文 glyph 和映射表预加载到普通 RAM，再让查表 hook 指向 RAM 表。

## 2026-05-27 文件预加载原型

已新增：

```text
tools/patch_vram_font_file_preload_probe.py
rom/test_vram_font_file_preload_probe.nds
font/chs_probe.bin
```

`font/chs_probe.bin` 被加入 NitroFS，并在 `020869E0` 字体初始化尾部通过原文件加载函数 `0207F80C` 加载到普通 RAM。

运行时验证：

```text
chs_data_ptr  = 0x02282F40
chs_data_size = 0x000000A0
0x82CD -> R0=0x02282F60
0x82DF -> R0=0x02282FA0
```

详细记录见 `plan/cache/vram-font-bypass/file-preload-probe.md`。

结论：自定义 glyph 数据源已经从 ARM9 空洞迁移到 NitroFS 文件和普通 RAM。下一步应正式化文件格式，并补 1x1 路径验证。

## 2026-05-28 RAM 预加载容量压力测试

已新增：

```text
tools/run_font_preload_size_sweep.py
plan/cache/vram-font-bypass/preload-size-pressure.md
```

关键结论：

```text
512K/896K/960K/992K/1008K 均可进入文本绘制采样。
1008K 样本仍能命中：82CD -> 02286B80, 82DF -> 02286BC0。
1024K 样本分配后推进到文本流程失稳，未命中正常绘制样本。
1392K 起 chs_data_ptr=0，说明连续 RAM 分配失败。
```

方案判断：

- `0207F80C` 更像是整文件连续加载，不会自动分页。
- 不能把完整中文字模设计成接近或超过 1MB 的常驻 RAM 文件。
- 正式方案应拆为常驻 map/header + glyph page/chunk + VRAM 当前画面缓存。
- 保守设计线：单个常驻 chs 数据块不要超过 `896K`；`1008K` 只作为压力边界样本。

下一步仍是正式化文件格式，但格式应优先支持分页或分块 glyph 数据，而不是单一大文件常驻。

## 2026-05-28 1x1 路径验证

已新增：

```text
rom/test_vram_font_file_preload_1x1_probe.nds
plan/cache/vram-font-bypass/1x1-path-probe.md
```

no-op 采样确认 1x1 样本：

```text
current_char=0x8140 R0=0x06880000 R1=0x06894000 R2=0x20 LR=0x02089194
```

RAM 文件替换 probe 确认：

```text
0x82BD, R2=0x20 -> R0=0x02282FA0
0x82A2, R2=0x20 -> R0=0x02282F60
```

结论：

- 1x1 和 1x2 复用 `02089190 -> 020087BC`。
- 1x1 复制大小为 `0x20`，glyph 源基址为 `0x06880000`。
- 现有 copy hook 也可以服务 1x1，只要给出正确 RAM glyph 地址。

新增约束：

当前 probe 只按 `char_code` 查表，导致 `0x82A2` 在 1x2 和 1x1 样本中都会被替换。正式格式必须把 `mode` 或 `glyph_size` 纳入 key，或者拆成 1x1/1x2 两套 map。下一步设计优先选“两套 map”，减少 hook 代码复杂度。

## 2026-05-28 split-map 原型验证

已新增：

```text
tools/patch_vram_font_split_map_probe.py
rom/test_vram_font_split_map_probe_v2.nds
plan/cache/vram-font-bypass/split-map-probe.md
```

当前原型把自定义字体数据拆成四个 NitroFS 文件：

```text
font/chs_1x1.map
font/chs_1x1.chunk
font/chs_1x2.map
font/chs_1x2.chunk
```

运行时加载指针：

```text
1x1 map   -> 0x02282F80 size 0x14
1x1 chunk -> 0x02282FC0 size 0x40
1x2 map   -> 0x02283020 size 0x1C
1x2 chunk -> 0x02283060 size 0xC0
```

MCP 采样确认同一个字符码可按 `R2` 分流：

```text
0x82A2, R2=0x40 -> R0=0x02283060  (1x2 chunk)
0x82A2, R2=0x20 -> R0=0x02282FC0  (1x1 chunk)
0x82CD, R2=0x40 -> R0=0x022830A0
0x82DF, R2=0x40 -> R0=0x022830E0
0x82BD, R2=0x20 -> R0=0x02282FE0
```

结论：

- 两套 map/chunk 的早期实现路线成立。
- `R2=0x20/0x40` 足以在 `02089190` copy hook 处区分 1x1/1x2。
- 下一步应把 split-map 原型提升为正式格式草案，补 magic/version/header/entry flags，并设计 glyph chunk 分页或分块加载策略。

## 2026-05-28 formal v0 格式验证

已新增：

```text
tools/patch_vram_font_formal_format_probe.py
rom/test_vram_font_formal_format_probe.nds
plan/cache/vram-font-bypass/formal-format-design.md
```

formal v0 文件格式已固定为：

```text
map   magic="CHMP", header_size=0x20, entry_size=0x10
chunk magic="CHCK", header_size=0x20, compression=0
```

map entry：

```text
u32 char_code
u32 glyph_offset      ; offset from chunk file start
u16 advance
u16 flags
u16 chunk_id
u16 reserved
```

MCP 采样确认 header-aware hook 可用：

```text
1x1 map/chunk -> 02282F80 / 02282FE0
1x2 map/chunk -> 02283060 / 022830E0

0x82A2, R2=0x40 -> R0=0x02283100  (1x2 chunk + 0x20)
0x82A2, R2=0x20 -> R0=0x02283000  (1x1 chunk + 0x20)
0x82CD, R2=0x40 -> R0=0x02283140
0x82DF, R2=0x40 -> R0=0x02283180
0x82BD, R2=0x20 -> R0=0x02283020
```

结论：

- split-map 已升级为带 magic/version/header/entry flags 的 formal v0。
- 当前 ARM9 hook 只读取 `entry_count/char_code/glyph_offset`，其余字段作为正式契约保留。
- 下一步转入 chunk 分页/分块设计：明确 `chunk_id`、chunk table、缺字 fallback、线性查找到排序/二分查找的迁移条件。

## 2026-05-28 chunk_id fallback 原型验证

已新增：

```text
tools/patch_vram_font_chunk_fallback_probe.py
rom/test_vram_font_chunk_fallback_probe.nds
plan/cache/vram-font-bypass/chunk-fallback-design.md
plan/cache/vram-font-bypass/chunk-fallback-samples.json
```

当前原型在 formal v0 的 `chunk_id` 字段上增加最小运行时分支：

```text
chunk_id == 0 -> R0 = chunk_base + glyph_offset
chunk_id != 0 -> R0 = chunk_base + 0x20
```

其中 `0x20` 是 chunk header 大小，也作为当前 chunk 内的 fallback glyph offset。

MCP 采样确认：

```text
0x82CD, R2=0x40 -> R0=0x02283120  fallback, chunk_id=1
0x82BD, R2=0x20 -> R0=0x02283000  fallback, chunk_id=1
0x82A2, R2=0x40 -> R0=0x02283160  resident, chunk_id=0
0x82A2, R2=0x20 -> R0=0x02283020  resident, chunk_id=0
0x82DF, R2=0x40 -> R0=0x022831A0  resident, chunk_id=0
```

结论：
- `chunk_id` 可以进入当前 copy hook 的运行时决策。
- 未驻留 chunk 不必落回原日文字形，可以稳定转向显式 fallback glyph。
- 下一步应补正式 chunk table、按页加载和失败 fallback 规则。

## 2026-05-28 chunk table 设计草案

阶段缓存：

```text
plan/cache/vram-font-bypass/chunk-table-design.md
```

当前设计判断：
- 不把 NitroFS 加载塞进 `02089190` copy hook；该位置先只负责快速查表和 fallback。
- 先为 1x1/1x2 各验证一个 resident slot：`entry.chunk_id == resident_slot.chunk_id` 时使用 resident chunk，否则 fallback。
- 真实 chunk 加载后续放到绘制前预扫、专门调度点或更高层缓存管理里验证。

下一次 runtime probe 应覆盖：

```text
chunk_id=0, resident_slot=0 -> resident glyph
chunk_id=1, resident_slot=0 -> fallback glyph
chunk_id=1, resident_slot=1 -> resident glyph
```

## 2026-05-28 resident-slot probe 结果

已新增：

```text
tools/patch_vram_font_chunk_table_probe.py
rom/test_vram_font_chunk_table_probe.nds
plan/cache/vram-font-bypass/chunk-table-samples.json
```

静态限制：

```text
copy_hook_size = 0xC0
0x02074140..0x02074200 已用满
```

MCP 已验证 1x2 resident-slot 分支：

```text
resident_1x2_chunk_id = 1
0x82CD, R2=0x40 -> R0=0x022831A0  resident hit
0x82DF, R2=0x40 -> R0=0x02283120  fallback
0x82A2, R2=0x40 -> R0=0x02283120  fallback
```

1x1 补充验证：

```text
tools/patch_vram_font_chunk_table_probe.py --char-1x1-extra-chunk-id 0
rom/test_vram_font_chunk_table_1x1_probe.nds
plan/cache/vram-font-bypass/chunk-table-1x1-samples.json
```

补充样本：

```text
0x82BD, R2=0x20 -> R0=0x02283040  resident_1x1=0, chunk_id=0, resident hit
```

结论：
- 单 resident slot 的 resident/fallback 分支已覆盖 1x1 与 1x2。
- 后续不能继续无规划扩展当前 copy hook；需要移动代码区或先做查找逻辑瘦身。

## 2026-05-28 hook 瘦身与同空洞迁移

新增：

```text
tools/patch_vram_font_chunk_table_slim_moved_probe.py
rom/test_vram_font_chunk_table_slim_moved_probe.nds
plan/cache/vram-font-bypass/hook-slim-relocate-probe.md
plan/cache/vram-font-bypass/chunk-table-slim-moved-samples.json
```

本次 probe 把 copy hook 的 literal 压缩为单个 `vars_base`，并把 load hook 从 `0x02074200` 后移到 `0x02074220`。

静态结果：

```text
copy_hook_size = 0xA0
copy_budget    = 0xE0
copy_margin    = 0x40
load_hook_addr = 0x02074220
load_hook_size = 0x11C
```

MCP 样本确认 resident/fallback 行为未破坏：

```text
0x82CD, R2=0x40 -> R0=0x022831A0  1x2 resident hit
0x82DF, R2=0x40 -> R0=0x02283120  1x2 fallback
0x82BD, R2=0x20 -> R0=0x02283040  1x1 resident hit
```

结论：
- 当前已经完成一次可运行的 hook 瘦身与代码区重排。
- 这只是 `0x0207411C` 主空洞内的局部迁移，不是迁到远端新洞。
- 后续可利用 `0x40` 余量验证极小多 slot 或 miss flag；真实缺页加载仍应放到 copy hook 外。

## 2026-05-28 chunk miss flag 原型

新增：

```text
tools/patch_vram_font_chunk_table_miss_flag_probe.py
rom/test_vram_font_chunk_table_miss_flag_probe.nds
plan/cache/vram-font-bypass/chunk-table-miss-flag-probe.md
plan/cache/vram-font-bypass/chunk-table-miss-flag-samples.json
```

变量布局：

```text
0x020743C4  miss_flag
0x020743C8  miss_char
0x020743CC  miss_chunk_id
0x020743D0  miss_mode
```

静态结果：

```text
copy_hook_size = 0xC0
copy_budget    = 0xE0
copy_margin    = 0x20
```

MCP 样本：

```text
0x82CD, R2=0x40 -> R0=0x022831A0, miss_flag=0
0x82DF, R2=0x40 -> R0=0x02283120, miss=1/82DF/0/0x40
0x82A2, R2=0x40 -> R0=0x02283120, miss=1/82A2/0/0x40
0x82BD, R2=0x20 -> R0=0x02283040, miss_flag=0
```

结论：
- resident slot 不匹配时可以稳定记录 miss 状态，同时继续 fallback。
- 当前只清 `miss_flag`，其余 miss 字段可能保留旧值；后续读取方必须以 `miss_flag==1` 为有效条件。
- 下一步应设计 miss 消费点：绘制前预扫、文本块切换点，或专门的 chunk 加载调度点。

## 2026-05-28 chunk miss consumer 原型

新增：

```text
tools/patch_vram_font_chunk_table_miss_consumer_probe.py
rom/test_vram_font_chunk_table_miss_consumer_probe.nds
plan/cache/vram-font-bypass/chunk-table-miss-consumer-probe.md
plan/cache/vram-font-bypass/chunk-table-miss-consumer-samples.json
```

本次在 `0x0208913C` 绘制入口增加 consumer hook，消费上一轮 copy hook 记录的 miss，并更新 resident slot id：

```text
0x020743D4  resident_1x1_chunk_id
0x020743D8  resident_1x2_chunk_id
```

静态结果：

```text
copy_hook_size = 0xC0
copy_budget    = 0xE0
consume_hook   = 0x02073D64 size=0x50
```

MCP 样本：

```text
0x82DF, R2=0x40 -> R0=0x02283120, miss=1/82DF/0/0x40, resident_1x2=1
next entry consumes miss -> resident_1x2=0, miss_flag=0
0x82A2, R2=0x40 -> R0=0x02283160, resident hit under resident_1x2=0
```

结论：
- `0x0208913C` 可以作为 copy hook 外的 miss 消费点。
- 单 slot 的 miss 消费会让 resident slot id 翻转，证明 producer/consumer 接口成立。
- 该原型还没有真实加载 chunk 数据，只是验证调度点和状态传递；下一步应把消费动作替换为加载/搬运目标 chunk。

## 2026-05-28 resident copy v2 原型

新增：

```text
tools/patch_vram_font_chunk_table_resident_copy_probe.py
rom/test_vram_font_chunk_table_resident_copy_v2_probe.nds
plan/cache/vram-font-bypass/chunk-table-resident-copy-probe.md
plan/cache/vram-font-bypass/chunk-table-resident-copy-v2-samples.json
```

v1 使用固定 ARM9 空洞作为 resident buffer，MCP 样本显示进入文本前该地址已被运行时数据污染。v2 改为让 `chs_1x2.chunk` 自带 resident page：

```text
0x000  CHPK header
0x020  resident page
0x100  source page 0
0x1E0  source page 1
```

静态结果：

```text
copy_hook_size    = 0xCC
copy_budget       = 0xE0
consume_hook      = 0x02073D64 size=0x90
1x2_chunk size    = 0x2C0
```

MCP 样本：

```text
1x2_chunk_ptr = 0x02283100
resident page = 0x02283120
0x82DF -> R0=0x02283140, data=C77CC77C C77CC77C, miss=1/82DF/0/0x40
next entry -> resident_1x2=0, miss_flag=0
0x82A2 -> R0=0x02283180, data=73377337 73377337
```

结论：
- `0x0208913C` consumer 可以执行真实 page copy，不只是更新 resident slot id。
- resident buffer 放在 chunk heap 内更稳定，不依赖静态空洞是否运行时安全。
- 当前单 slot 会在 `82DF/82A2` 与 `82CD` 所属 chunk 之间来回失效，后续缓存设计至少需要双 slot 或更高层预扫。
