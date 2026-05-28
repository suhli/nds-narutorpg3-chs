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
