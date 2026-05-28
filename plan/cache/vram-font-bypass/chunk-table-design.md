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

## 2026-05-28 hook 瘦身与 load hook 后移

新增 probe：

```text
tools/patch_vram_font_chunk_table_slim_moved_probe.py
rom/test_vram_font_chunk_table_slim_moved_probe.nds
plan/cache/vram-font-bypass/hook-slim-relocate-probe.md
plan/cache/vram-font-bypass/chunk-table-slim-moved-samples.json
```

布局变化：

```text
copy hook: 0x02074140, size 0xA0
load hook: 0x02074220, size 0x11C
copy budget: 0xE0
copy margin: 0x40
```

验证样本：

```text
0x82CD, R2=0x40 -> R0=0x022831A0  resident hit
0x82DF, R2=0x40 -> R0=0x02283120  fallback
0x82BD, R2=0x20 -> R0=0x02283040  resident hit
```

判断：
- `0x0207411C` 主空洞内部重排可行。
- copy hook 已释放出 `0x40` 字节余量，可承载很小的状态记录或 slot 扩展。
- 若要加入二分查找、缺页加载或更复杂 chunk table，仍应迁移到独立代码区或改为热路径外调度。

## 2026-05-28 miss flag 原型

新增 probe：

```text
tools/patch_vram_font_chunk_table_miss_flag_probe.py
rom/test_vram_font_chunk_table_miss_flag_probe.nds
plan/cache/vram-font-bypass/chunk-table-miss-flag-probe.md
plan/cache/vram-font-bypass/chunk-table-miss-flag-samples.json
```

miss 状态记录在变量区末尾：

```text
0x020743C4  miss_flag
0x020743C8  miss_char
0x020743CC  miss_chunk_id
0x020743D0  miss_mode
```

验证样本：

```text
0x82DF, R2=0x40 -> R0=0x02283120, miss=00000001 000082DF 00000000 00000040
0x82A2, R2=0x40 -> R0=0x02283120, miss=00000001 000082A2 00000000 00000040
0x82CD, R2=0x40 -> R0=0x022831A0, miss_flag=0
0x82BD, R2=0x20 -> R0=0x02283040, miss_flag=0
```

判断：
- copy hook 可作为 miss 生产者，但不应承担 miss 消费和 NitroFS 加载。
- miss 字段为后续 chunk loader 提供最小接口：mode、char、chunk_id。
- 该版本 copy hook size 回到 `0xC0`，在后移后的 `0xE0` budget 内还剩 `0x20`。

## 2026-05-28 miss consumer 原型

新增 probe：

```text
tools/patch_vram_font_chunk_table_miss_consumer_probe.py
rom/test_vram_font_chunk_table_miss_consumer_probe.nds
plan/cache/vram-font-bypass/chunk-table-miss-consumer-probe.md
plan/cache/vram-font-bypass/chunk-table-miss-consumer-samples.json
```

新增入口 hook：

```text
0x0208913C -> 0x02073D64
consume_hook_size = 0x50
```

变量区扩展：

```text
0x020743D4  resident_1x1_chunk_id
0x020743D8  resident_1x2_chunk_id
```

验证样本：

```text
0x82DF -> R0=0x02283120, miss_flag=1, miss_chunk_id=0, resident_1x2=1
next entry -> miss_flag=0, resident_1x2=0
0x82A2 -> R0=0x02283160, resident hit
```

判断：
- `0208913C` 是可用的 miss 消费点，位置高于 `02089190` copy hook。
- 该消费点可先更新 resident slot，再由后续 copy hook 正常命中。
- 当前只是 slot id 原型；真实实现还需补 chunk 数据换入和失败恢复。

## 2026-05-28 resident copy v2 原型

新增 probe：

```text
tools/patch_vram_font_chunk_table_resident_copy_probe.py
rom/test_vram_font_chunk_table_resident_copy_v2_probe.nds
plan/cache/vram-font-bypass/chunk-table-resident-copy-probe.md
plan/cache/vram-font-bypass/chunk-table-resident-copy-v2-samples.json
```

v2 的 `chs_1x2.chunk` pack：

```text
0x000  CHPK header
0x020  resident page
0x100  source page 0
0x1E0  source page 1
total  0x2C0
```

copy hook 仍只做快速查表和 R0 决策；1x2 命中路径从 `chunk_ptr + 0x20` 读 resident page。consumer 在 `0x0208913C` 读取 miss 后，在同一 heap buffer 内搬运：

```text
dst = chunk_ptr + 0x20
src = chunk_ptr + 0x100  ; chunk 0
src = chunk_ptr + 0x1E0  ; chunk 1
size = 0xE0
```

静态结果：

```text
copy_hook_size    = 0xCC
copy_budget       = 0xE0
consume_hook_size = 0x90
vars_end          = 0x020743DC
```

验证样本：

```text
1x2_chunk_ptr = 0x02283100
resident page = 0x02283120
82CD -> R0=022831C0, data=95599559, resident_1x2=1
82DF -> R0=02283140, data=C77CC77C, miss_chunk_id=0
consumer -> resident_1x2=0
82A2 -> R0=02283180, data=73377337
82CD -> R0=02283140, data=B66BB66B, miss_chunk_id=1
```

判断：
- chunk table 的 resident page 可以和源 page 放在同一个 heap buffer，避免固定 RAM 空洞污染。
- 单 slot 缓存策略已经暴露抖动问题，正式格式需要支持多 resident slot、预扫，或更高层调度。
- copy hook size `0xCC` 仍在 `0xE0` budget 内，但只剩 `0x14`，后续复杂逻辑不应继续塞进 copy hook。

## 2026-05-28 dual-slot 1x2 原型

新增 probe：

```text
tools/patch_vram_font_chunk_table_dual_slot_probe.py
rom/test_vram_font_chunk_table_dual_slot_v2_probe.nds
plan/cache/vram-font-bypass/chunk-table-dual-slot-probe.md
plan/cache/vram-font-bypass/chunk-table-dual-slot-v2-samples.json
```

`chs_1x2.chunk` dual-slot pack：

```text
0x000  CHP2 header
0x020  resident slot0
0x100  resident slot1
0x1E0  source page0
0x2C0  source page1
total  0x3A0
```

变量区：

```text
0x020743D8  resident_1x2_slot0_chunk_id
0x020743DC  resident_1x2_slot1_chunk_id
0x020743E0  resident_1x2_next_slot
```

代码区：

```text
0x02074140  copy trampoline, size=0x4
0x02073D64  copy hook body, size=0xCC
0x020743E4  consume hook, size=0xB8
```

验证样本：

```text
82CD -> R0=022831C0, data=95599559, slot0=1, slot1=FFFFFFFF
82DF -> R0=02283140, data=C77CC77C, miss_chunk_id=0
consumer -> slot0=1, slot1=0, next=0
82A2 -> R0=02283260, data=73377337
82C6 -> R0=022831C0, data=95599559
```

判断：
- 双 slot 能保留旧 chunk，同时加载新 chunk，已解决双 chunk 样本中的单 slot 抖动。
- copy 主体迁到 `0x02073D64` 后，原 copy patch 点只需 trampoline；这是后续复杂查找/缓存逻辑更现实的代码布局。
- 该 probe 暂时只接管 1x2，正式 chunk table 仍需把 1x1 slot 与更多 chunk 的替换策略补齐。

## 2026-05-28 dual-mode 1x1/1x2 原型

新增 probe：
```text
tools/patch_vram_font_chunk_table_dual_mode_probe.py
rom/test_vram_font_chunk_table_dual_mode_probe.nds
plan/cache/vram-font-bypass/chunk-table-dual-mode-probe.md
plan/cache/vram-font-bypass/chunk-table-dual-mode-long-samples.json
```

关键布局：
```text
0x02074140  copy trampoline, size=0x4
0x02073D64  copy hook body, size=0xE8
0x020743E4  consume hook, size=0xB8
0x020743D4  resident_1x1_chunk_id
0x020743D8  resident_1x2_slot0_chunk_id
0x020743DC  resident_1x2_slot1_chunk_id
0x020743E0  resident_1x2_next_slot
```

验证样本：
```text
8140/R2=0x40 -> R0=02284B60, data=84488448
8140/R2=0x20 -> R0=02283040, data=41144114
82BD/R2=0x20 -> R0=02283060, data=62266226
82DF/R2=0x40 -> miss=1/82DF/0/0x40
82A2/R2=0x40 -> R0=02284C40, data=73377337, slot0=1, slot1=0
82C6/R2=0x40 -> R0=02284BA0, data=95599559, slot0=1, slot1=0
```

判断：
- dual-mode 原型已补齐 1x1/1x2 同 hook 分流，不再只是 1x2 缓存实验。
- `0x8140` 同字符码在两种 mode 下读到不同图样，证明 split-map 与 chunk table 结合后不会互相污染。
- 1x2 双 slot 的换页和保留旧 chunk 行为没有被 1x1 分支破坏。
- 1x1 目前仍只有单 resident id；正式实现需要决定 1x1 是否也做多 slot，或保持常用 1x1 chunk 常驻。

## 2026-05-28 dual-mode 1x1 page copy 原型

新增 probe：
```text
tools/patch_vram_font_chunk_table_dual_mode_1x1_copy_probe.py
rom/test_vram_font_chunk_table_dual_mode_1x1_copy_probe.nds
plan/cache/vram-font-bypass/chunk-table-dual-mode-1x1-copy-probe.md
plan/cache/vram-font-bypass/chunk-table-dual-mode-1x1-copy-long-samples.json
```

代码区：
```text
0x02073D64  copy hook body, size=0xEC
0x020743E4  consume trampoline, size=0x8
0x020718D8  consume body, size=0xFC
```

1x1 pack：
```text
0x020 resident page
0x0A0 source page0
0x120 source page1
```

验证样本：
```text
8140/R2=0x20 -> R0=02283040, data=A66AA66A, miss=1/8140/1/0x20
8140/R2=0x20 -> R0=02283060, data=41144114, resident_1x1=1
82A2/R2=0x40 -> R0=02284C40, data=73377337
82C6/R2=0x40 -> R0=02284BA0, data=95599559
```

判断：
- 1x1 miss consumer 链路成立，不再只是更新 resident id。
- 当前 1x1 page copy 已在 `0x020718D8` 空洞内支持 `chunk_id=0/1` 两页选择；正式 chunk table 若扩展更多 page，应迁移到更大代码区或抽出通用 copy 例程。

## 2026-05-28 集成构建与冒烟

新增：
```text
tools/build_vram_font_dynamic_cache_rom.py
tools/run_vram_font_integrated_smoke.py
plan/cache/vram-font-bypass/integrated-build-and-smoke.md
rom/narutorpg3_chs_dynamic_font_v0.nds
plan/cache/vram-font-bypass/integrated-smoke-samples.json
```

构建入口支持默认样本字体，也支持 `--font-dir` 传入外部 `chs_1x1.map/chunk` 与 `chs_1x2.map/chunk`。集成冒烟一次性覆盖：
```text
1x1 miss -> resident page copy
1x1 resident hit
1x2 shared char mode isolation
1x2 dual-slot slot1 hit
1x2 dual-slot slot0 retained hit
final emulator running state
```

判断：
- 后续停止继续做单点 probe，改为集成构建后跑一次整体验收。
- 如果整体验收失败，再根据失败项拆分为 1x1 miss、1x2 slot、路径加载或代码区迁移问题。
