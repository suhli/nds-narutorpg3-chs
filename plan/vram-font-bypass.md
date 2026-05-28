# 绕过 VRAM 全量字体加载方案

## 背景

当前汉化路线的第一优先级是解决中文字库和字模承载问题。已有逆向笔记表明，原游戏字体系统会通过 `FUN_overlay_0__02086870` 从 NitroFS 加载字体文件，并把 `.chr` 字模拷贝到 `0x06880000` 附近的 VRAM 字体区域。

这个方案对原日文字库可行，但对汉化不稳妥：中文需要的字形数量明显更多，完整中文字模大概率无法常驻当前 VRAM 字体区域。因此本计划的目标不是扩容后继续把全量字库塞进 VRAM，而是优先尝试绕过“全量字库/字模从 VRAM 加载或常驻”的路径。

## 必要上下文

- 原版 ROM：`rom/origin.nds`，只读，不覆盖，不原地 patch。
- 字体入口笔记：`hack/字体加载入口.md`。
- 已知字体加载核心函数：`FUN_overlay_0__02086870`。
- 已知 NitroFS 读取函数：`FUN_overlay_0__0207f80c`。
- 当前字体 tile VRAM 映射地址：`0x06880000`。
- 字体系统全局结构体：`DAT_020B73E0`。
- `DAT_020B73E0 + 0x20` 指向 `font_1x1.tbl`，运行时值为 `0x0688E6C0`。
- `DAT_020B73E0 + 0x24` 是 `font_1x1.tbl` 项计数，运行时值为 `0xE0`。
- `DAT_020B73E0 + 0x28` 指向 `font_1x2.tbl`，运行时值为 `0x0688EA40`。
- `DAT_020B73E0 + 0x2C` 是 `font_1x2.tbl` 项计数，运行时值为 `0x32B`。
- 运行时已确认 `.tbl` 也在 VRAM 字体区域，不是普通 RAM 驻留表。
- 当前理解的绘制链路：读取文本编码 -> 查 `tbl` 得到 tile index -> 从 VRAM tile 区读取字形 -> 绘制。
- ROM 解包/打包按 `.codex/skills/ndstool-rom-workflow/SKILL.md`。
- 模拟器和运行时调试按 `.codex/skills/desmume-mcp-workflow/SKILL.md`。
- 2026-05-27 已验证新版 DeSmuME MCP 支持按键、触摸、释放全部和截图工具，可用于推进正文/菜单运行时断点。

## 目标

- 找到文本绘制函数中“字符编码到 tile index，再到 VRAM tile”的完整链路。
- 明确最小 patch 点：是在加载阶段改、在查表阶段改，还是在绘制前动态补 tile。
- 设计并验证一个不需要全量中文字模常驻 VRAM 的方案。
- 形成可回写 ROM 的技术路线，供后续 dump 日文和汉化回写使用。

## 非目标

- 本阶段不开始大规模 dump 日文文本。
- 本阶段不开始翻译。
- 本阶段不直接覆盖 `rom/origin.nds`。
- 本阶段不把“扩大 VRAM 地址范围并继续塞全量中文字库”作为主路线，只作为对照验证。

## 候选方案

### 方案 A：动态 VRAM 字形缓存

思路：

- 字库/字模主体放在 ROM 或普通 RAM。
- VRAM 中只保留当前画面实际用到的字形 tile。
- 绘制字符前检查该字形是否已在 VRAM 缓存中。
- 如果不存在，把字模复制到 VRAM 的一个缓存槽，并更新字符到 tile index 的映射。

优点：

- 最符合“绕过全量 VRAM 常驻”的目标。
- 理论上支持远大于 VRAM 容量的中文字库。

风险：

- 需要找到安全的 VRAM 字形缓存区域和替换时机。
- 需要处理 tile 淘汰、同屏复用、窗口刷新和文本滚动。
- 如果绘制函数只接受静态 `tbl`，需要 hook 查表或绘制入口。

### 方案 B：文本场景预扫描 + 分页字库

思路：

- 每次进入对话、菜单或场景前，预扫描该段文本需要的字。
- 将本段文本所需字形批量加载到 VRAM。
- 当前段落结束后换页或重载字形集合。

优点：

- 运行时逻辑比逐字动态缓存简单。
- 如果脚本文本边界明确，稳定性更高。

风险：

- 必须先理解脚本/文本块边界。
- 菜单、道具名、战斗文本等动态组合文本可能不好预扫描。

### 方案 C：保留原字库 + 少量汉字覆盖验证

思路：

- 先不做完整动态系统，只替换少量字形或临时把部分汉字映射到已有 tile。
- 用于验证绘制链路、宽度、1x1/1x2、调色板和断点。

优点：

- 风险低，适合确认 patch 点。

风险：

- 不能解决最终汉化容量问题，只能作为实验阶段。

## 阶段计划

### 1. 静态复核字体加载和绘制链路

状态：已完成。

目标：

- 从已知入口 `FUN_overlay_0__02086870` 反推调用者和后续绘制函数。
- 确认 `.chr`、`.tbl`、`.plt` 的加载地址、大小和使用位置。
- 找到实际从 `DAT_020B73E0 + 0x20/+0x28` 读取 `tbl`，并从 `+0x24/+0x2C` 读取项计数的函数。

产物：

- `hack/字体绘制链路.md`
- 阶段缓存：`plan/cache/vram-font-bypass/static-render-chain.md`

### 2. 运行时确认关键地址和数据流

状态：已完成。

目标：

- 用 DeSmuME MCP 加载测试 ROM 或原版 ROM进行只读调试。
- 在 `0207F80C`、`02086870`、`0208689C`、`DAT_020B73E0` 相关位置设置断点或读取内存。
- 确认文本出现时 ARM9 PC、寄存器、`tbl` 指针、VRAM tile 地址的关系。
- 使用 MCP 输入工具推进到正文/菜单界面，并用截图记录关键可见状态。

产物：

- `hack/字体运行时观察.md`
- 阶段缓存：`plan/cache/vram-font-bypass/runtime-observation.md`
- MCP 更新缓存：`plan/cache/vram-font-bypass/desmume-mcp-update.md`

### 3. 设计最小可验证 patch

状态：已完成。

目标：

- 选择一个最低风险的验证点。
- 优先考虑“单字/少数字形动态写入 VRAM 缓存槽”。
- 明确 patch 地址、输入输出、需要保存/恢复的寄存器、可用空洞或新增代码位置。
- 明确如何构建测试 ROM，输出为新文件，不覆盖原版。

产物：

- `hack/字体动态缓存方案.md`
- 阶段缓存：`plan/cache/vram-font-bypass/minimal-patch-design.md`

### 4. 构建最小实验 ROM

状态：已完成。

目标：

- 使用 `ndstool` 解包 ROM。
- 只做最小 patch 或替换最小字体资源。
- 重新打包为新的测试 ROM，例如 `rom/test_vram_font_bypass.nds`。
- 不覆盖 `rom/origin.nds`。

产物：

- 测试 ROM：`rom/test_vram_font_hook_probe_arm9.nds`
- 阶段缓存：`plan/cache/vram-font-bypass/test-rom-build.md`

### 5. 模拟器验证和方案判定

状态：进行中。

目标：

- 使用 DeSmuME MCP 加载测试 ROM。
- 验证字符显示、VRAM 写入、断点触发、菜单/对话稳定性。
- 判定方案 A、B、C 哪个进入后续正式实现。

产物：

- `hack/字体绕过VRAM验证结论.md`
- 阶段缓存：`plan/cache/vram-font-bypass/verification-result.md`

## 决策标准

优先选择满足以下条件的方案：

- 不要求完整中文字模常驻 VRAM。
- 对原绘制系统侵入尽量小。
- 可通过小规模 patch 逐步验证。
- 能支持后续文本 dump 和汉化回写。
- 出错时容易回退，不破坏原版 ROM。

## 风险和待确认点

- `tbl` 是否只是静态字符到 tile index 映射，还是还包含宽度/形态信息。
- 1x1 和 1x2 字体是否在同一绘制路径中统一处理。
- VRAM 字体区域是否会被其他图形系统复用或覆盖。
- 是否存在 DMA 拷贝路径，不能只看 CPU 写入。
- 动态写 VRAM 的时机是否会和渲染扫描冲突。
- 文本控制符、换行、变量占位符是否影响预扫描或缓存策略。

## 当前入口

当前计划从“静态复核字体加载和绘制链路”开始。下一步不要直接 patch ROM，先补齐 `hack/字体绘制链路.md` 和阶段缓存。

## 2026-05-27 进度更新

阶段 5 的稳定性复核已经修正此前判断：`running=0 ARM9_PC=0x02089210 / ARM7_PC=0x00000020` 可以通过 `nds_resume` 继续运行，不能作为 glyph 替换崩溃证据。

已经确认：

- `0208914C` 保存当前字符码稳定。
- `02089190` copy hook 框架稳定。
- `0x82CD -> 0x02074180` 的按字符替换可进入 `020087BC`。
- `02074180` 中放原 glyph 副本或 test-pattern glyph 均可作为 RAM glyph 源。

当前决策：方案 A（动态 glyph 缓存）进入正式设计。下一阶段产物见 `plan/cache/vram-font-bypass/dynamic-cache-design.md`。

## 2026-05-27 追加进度

已完成：

- `tools/sample_vram_font_chars_mcp.py`：可复现采样 `020087BC` 命中时的 `current_char/R0/R1/R2`。
- `tools/patch_vram_font_table_hook_probe.py`：表驱动查找 hook 原型。
- `rom/test_vram_font_table_hook_probe.nds`：表驱动测试 ROM。

关键验证：

```text
0x82CD -> R0=0x02074200
0x82DF -> R0=0x02074240
```

当前下一步：设计 glyph 数据和映射表的 RAM 预加载方案，避免最终实现继续依赖 ARM9 空洞内的测试数据。

## 2026-05-27 RAM 预加载验证

已完成 NitroFS 文件预加载原型：

```text
tools/patch_vram_font_file_preload_probe.py
rom/test_vram_font_file_preload_probe.nds
font/chs_probe.bin
```

运行时验证：

```text
font/chs_probe.bin -> RAM 0x02282F40
0x82CD -> R0=0x02282F60
0x82DF -> R0=0x02282FA0
```

当前结论：动态字体方案已具备“ROM 文件 -> 普通 RAM -> 绘制 hook”的最小闭环。下一步正式化中文 glyph 文件格式，并验证 1x1 字体路径。

## 2026-05-28 RAM 容量压力验证

已新增压力测试脚本：

```text
tools/run_font_preload_size_sweep.py
```

阶段缓存：

```text
plan/cache/vram-font-bypass/preload-size-pressure.md
```

关键结果：

```text
512K/896K/960K/992K/1008K 可进入文本绘制采样。
1008K: 82CD -> 02286B80, 82DF -> 02286BC0。
1024K: 分配后文本流程失稳，未取得正常绘制样本。
1392K+: chs_data_ptr=0，连续 RAM 分配失败。
```

当前决策更新：

- 字库文件不能按“完整中文字模整包常驻 RAM”设计。
- 正式格式应拆为常驻 map/header 和可分页/分块加载的 glyph 数据。
- 映射表本身容量压力较小，先压垮 RAM 的是 `0x40 bytes/glyph` 的 1x2 glyph 数据。
- 单个常驻 chs 数据块按保守线控制在 `896K` 以内；超过 1MB 的数据必须分块、按需加载或压缩后分段展开。

## 2026-05-28 1x1 路径验证

已完成 1x1 字体路径采样和 RAM glyph 替换验证。

新增测试 ROM：

```text
rom/test_vram_font_file_preload_1x1_probe.nds
```

阶段缓存：

```text
plan/cache/vram-font-bypass/1x1-path-probe.md
```

关键结果：

```text
1x1 基线：R0=06880000, R2=0x20, LR=02089194
1x1 替换：82BD -> R0=02282FA0, R2=0x20
1x1 替换：82A2 -> R0=02282F60, R2=0x20
```

当前决策更新：

- 1x1 与 1x2 复用 `02089190 -> 020087BC`，copy hook 可同时服务两条路径。
- 正式 map 不能只按 `char_code` 命中；同一字符在 1x1/1x2 中可能需要不同 glyph。
- 下一步正式文件格式优先拆成 `chs_1x1.map/chunk` 与 `chs_1x2.map/chunk`，减少早期 hook 的 mode 分支复杂度。

## 2026-05-28 split-map 原型验证

已新增 split-map 测试脚本与 v2 ROM：

```text
tools/patch_vram_font_split_map_probe.py
rom/test_vram_font_split_map_probe_v2.nds
plan/cache/vram-font-bypass/split-map-probe.md
```

已验证四文件结构：

```text
font/chs_1x1.map
font/chs_1x1.chunk
font/chs_1x2.map
font/chs_1x2.chunk
```

关键运行时结果：

```text
1x1 map/chunk -> 02282F80 / 02282FC0
1x2 map/chunk -> 02283020 / 02283060

0x82A2, R2=0x40 -> R0=02283060
0x82A2, R2=0x20 -> R0=02282FC0
```

当前决策更新：

- `R2` 分流方案成立，可在 `02089190` copy hook 处区分 1x1/1x2。
- split-map 比单文件 `chs_probe.bin` 更接近正式实现，后续以两套 map/chunk 为早期主线。
- 下一步进入正式格式草案：补 magic/version/header/entry flags，并设计 glyph chunk 分页或分块加载。

## 2026-05-28 formal v0 格式验证

已新增正式格式测试：

```text
tools/patch_vram_font_formal_format_probe.py
rom/test_vram_font_formal_format_probe.nds
plan/cache/vram-font-bypass/formal-format-design.md
```

当前格式：

```text
map   = "CHMP" + 0x20-byte header + 0x10-byte entries
chunk = "CHCK" + 0x20-byte header + glyph data
```

关键验证结果：

```text
1x1 map/chunk -> 02282F80 / 02282FE0
1x2 map/chunk -> 02283060 / 022830E0

0x82A2, R2=0x40 -> R0=02283100
0x82A2, R2=0x20 -> R0=02283000
```

当前决策更新：

- formal v0 已验证，可作为后续动态字体文件格式基础。
- `glyph_offset` 从 chunk 文件起点计算，第一枚 glyph offset 为 `0x20`。
- 下一步进入 chunk 分页/分块设计，重点是 `chunk_id`、chunk table、缺字 fallback 和查找性能。

## 2026-05-28 chunk_id fallback 原型验证

已新增测试 ROM 与阶段缓存：

```text
tools/patch_vram_font_chunk_fallback_probe.py
rom/test_vram_font_chunk_fallback_probe.nds
plan/cache/vram-font-bypass/chunk-fallback-design.md
```

本次验证在 formal v0 entry 的 `chunk_id` 字段上增加最小分支：

```text
chunk_id == 0 -> 使用 entry.glyph_offset
chunk_id != 0 -> 使用 chunk_base + 0x20 fallback glyph
```

关键运行时样本：

```text
0x82CD, R2=0x40 -> R0=02283120  fallback
0x82BD, R2=0x20 -> R0=02283000  fallback
0x82A2, R2=0x40 -> R0=02283160  resident
0x82A2, R2=0x20 -> R0=02283020  resident
```

当前决策更新：
- formal v0 继续作为文件格式基础。
- `chunk_id != 0` 可先落到显式 fallback glyph，后续再替换为真实 chunk table + 按页加载。
- 下一步重点转为 chunk table 格式、chunk resident 状态、加载失败恢复和 map 查找优化。

## 2026-05-28 chunk table 设计草案

新增阶段缓存：

```text
plan/cache/vram-font-bypass/chunk-table-design.md
```

当前设计判断：
- `02089190` copy hook 暂不承担 NitroFS 缺页加载，只做 `char_code -> chunk_id/glyph_offset -> resident/fallback` 的快速决策。
- 先验证单 resident slot：`entry.chunk_id == resident_slot.chunk_id` 时命中 resident chunk，否则命中 fallback glyph。
- 真实按页加载应放到绘制前预扫、专门调度点或更高层缓存管理里，避免逐字绘制时同步读文件。

## 2026-05-28 resident-slot probe 结果

新增测试 ROM：

```text
tools/patch_vram_font_chunk_table_probe.py
rom/test_vram_font_chunk_table_probe.nds
plan/cache/vram-font-bypass/chunk-table-samples.json
```

关键限制：

```text
copy_hook_size = 0xC0
COPY_HOOK_ADDR=0x02074140
LOAD_HOOK_ADDR=0x02074200
```

当前 copy hook 区间已经用满，后续复杂逻辑不能继续硬塞。

已验证：

```text
resident_1x2_chunk_id=1
0x82CD, R2=0x40 -> R0=022831A0  resident hit
0x82DF, R2=0x40 -> R0=02283120  fallback
```

未完成：
- 多 slot 和真实缺页加载仍未进入实现。

## 2026-05-28 1x1 resident-slot 补充验证

新增专用 ROM：

```text
rom/test_vram_font_chunk_table_1x1_probe.nds
plan/cache/vram-font-bypass/chunk-table-1x1-samples.json
```

构建参数：

```text
tools/patch_vram_font_chunk_table_probe.py --char-1x1-extra-chunk-id 0
```

关键运行时样本：

```text
0x82BD, R2=0x20 -> R0=02283040  resident hit
```

当前判断更新：
- 单 resident slot 的命中/未命中分支已覆盖 1x1 与 1x2。
- 当前 copy hook 已用满 `0x02074140..0x02074200`，下一步应先做 hook 瘦身或迁移代码区，再推进多 slot/二分查找/缺页调度。

## 2026-05-28 hook 瘦身与同空洞迁移验证

新增阶段缓存与测试 ROM：

```text
plan/cache/vram-font-bypass/hook-slim-relocate-probe.md
tools/patch_vram_font_chunk_table_slim_moved_probe.py
rom/test_vram_font_chunk_table_slim_moved_probe.nds
plan/cache/vram-font-bypass/chunk-table-slim-moved-samples.json
```

本次把 copy hook 压缩为只使用一个 `vars_base` literal，并把 load hook 从 `0x02074200` 后移到 `0x02074220`。这是在 `0x0207411C` 主空洞内部重排，不是远端代码洞迁移。

静态结果：

```text
copy_hook_size = 0xA0
copy_budget    = 0xE0
copy_margin    = 0x40
load_hook_addr = 0x02074220
load_hook_size = 0x11C
```

运行时关键样本：

```text
0x82CD, R2=0x40 -> R0=0x022831A0  1x2 resident hit
0x82DF, R2=0x40 -> R0=0x02283120  1x2 fallback
0x82BD, R2=0x20 -> R0=0x02283040  1x1 resident hit
```

当前判断更新：
- hook 瘦身和局部迁移没有破坏现有 resident/fallback 路径。
- copy hook 现在有 `0x40` 字节余量，可用于极小的多 slot 或 miss flag 验证。
- 复杂 chunk miss 加载、二分查找或完整调度逻辑仍不应塞进逐字 copy hook。

## 2026-05-28 chunk miss flag 原型验证

新增阶段缓存与测试 ROM：

```text
plan/cache/vram-font-bypass/chunk-table-miss-flag-probe.md
tools/patch_vram_font_chunk_table_miss_flag_probe.py
rom/test_vram_font_chunk_table_miss_flag_probe.nds
plan/cache/vram-font-bypass/chunk-table-miss-flag-samples.json
```

本次不做真实缺页加载，只在 resident slot 不匹配时记录最小 miss 状态：

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

运行时关键样本：

```text
0x82CD, R2=0x40 -> R0=0x022831A0, miss_flag=0
0x82DF, R2=0x40 -> R0=0x02283120, miss=1/82DF/0/0x40
0x82A2, R2=0x40 -> R0=0x02283120, miss=1/82A2/0/0x40
0x82BD, R2=0x20 -> R0=0x02283040, miss_flag=0
```

当前判断更新：
- copy hook 已能作为 chunk miss 生产者，把缺页所需的 `char/mode/chunk_id` 记录到 RAM。
- 只清 `miss_flag`，不清旧 `miss_char/miss_chunk_id/miss_mode`；读取方必须以 `miss_flag==1` 为有效条件。
- 下一步应找 miss 消费点或预扫调度点，避免在逐字 copy hook 中同步读 NitroFS。

## 2026-05-28 chunk miss consumer 原型验证

新增阶段缓存与测试 ROM：

```text
plan/cache/vram-font-bypass/chunk-table-miss-consumer-probe.md
tools/patch_vram_font_chunk_table_miss_consumer_probe.py
rom/test_vram_font_chunk_table_miss_consumer_probe.nds
plan/cache/vram-font-bypass/chunk-table-miss-consumer-samples.json
```

本次在 `0x0208913C` 绘制入口增加 consumer hook：

```text
0x0208913C -> 0x02073D64
consume_hook_size = 0x50
```

consumer 读取上一轮 copy hook 记录的 miss，并更新 resident slot id：

```text
0x020743D4  resident_1x1_chunk_id
0x020743D8  resident_1x2_chunk_id
```

运行时关键样本：

```text
0x82CD, R2=0x40 -> R0=0x022831A0, resident_1x2=1
0x82DF, R2=0x40 -> R0=0x02283120, miss=1/82DF/0/0x40, resident_1x2=1
next entry -> miss_flag=0, resident_1x2=0
0x82A2, R2=0x40 -> R0=0x02283160, resident hit
```

当前判断更新：
- miss producer/consumer 的最小接口成立。
- `0x0208913C` 比 `0x02089190` 更适合作为 miss 消费或加载调度入口。
- 当前只翻转 resident slot id，没有真实搬运 chunk；下一步应把 consumer 动作替换为 chunk 加载/搬运，并设计单 slot 失效后的恢复策略。

## 2026-05-28 chunk resident copy v2 验证

新增阶段缓存与测试 ROM：

```text
plan/cache/vram-font-bypass/chunk-table-resident-copy-probe.md
tools/patch_vram_font_chunk_table_resident_copy_probe.py
rom/test_vram_font_chunk_table_resident_copy_v2_probe.nds
plan/cache/vram-font-bypass/chunk-table-resident-copy-v2-samples.json
```

v1 把 resident buffer 放在固定 ARM9 空洞，运行时发现该区域会被其他数据污染；v2 改为把 resident page 放入 `chs_1x2.chunk` 自己的 heap buffer：

```text
chs_1x2.chunk:
  0x000  CHPK header
  0x020  resident page
  0x100  source page 0
  0x1E0  source page 1
total size = 0x2C0
```

静态结果：

```text
0x0208913C -> 0x02073D64
copy_hook_size    = 0xCC
copy_budget       = 0xE0
consume_hook_size = 0x90
load_hook         = 0x02074220 size=0x11C
```

运行时关键样本：

```text
1x2_chunk_ptr = 0x02283100
resident page = 0x02283120
0x82CD -> R0=0x022831C0, data=95599559 95599559, resident_1x2=1
0x82DF -> R0=0x02283140, data=C77CC77C C77CC77C, miss=1/82DF/0/0x40
next entry -> miss_flag=0, resident_1x2=0
0x82A2 -> R0=0x02283180, data=73377337 73377337
0x82CD -> R0=0x02283140, data=B66BB66B B66BB66B, miss=1/82CD/1/0x40
```

当前判断更新：
- consumer 能在 `0x0208913C` 层完成目标 page 到 heap 内 resident page 的搬运。
- copy hook 后续读取 resident page，能看到真实换页后的 glyph 数据。
- 单 1x2 resident slot 会在 chunk 0/1 之间抖动；下一步应验证双 slot 或文本块入口预扫策略。

## 2026-05-28 chunk table 双 slot 原型验证

新增阶段缓存与测试 ROM：

```text
plan/cache/vram-font-bypass/chunk-table-dual-slot-probe.md
tools/patch_vram_font_chunk_table_dual_slot_probe.py
rom/test_vram_font_chunk_table_dual_slot_v2_probe.nds
plan/cache/vram-font-bypass/chunk-table-dual-slot-v2-samples.json
```

本次把 1x2 resident 扩展为两个 slot：

```text
0x000  CHP2 header
0x020  resident slot0, initial page1
0x100  resident slot1, initially empty
0x1E0  source page0
0x2C0  source page1
total  0x3A0
```

copy hook 主体已超出原 `0x02074140..0x02074220` 热路径预算，因此迁到远端空洞：

```text
0x02074140  copy trampoline, size=0x4
0x02073D64  copy hook body, size=0xCC
0x020743E4  consume hook, size=0xB8
0x020743D8  resident_1x2_slot0_chunk_id
0x020743DC  resident_1x2_slot1_chunk_id
0x020743E0  resident_1x2_next_slot
```

运行时关键样本：

```text
1x2_chunk_ptr = 0x02283100
slot0 page    = 0x02283120
slot1 page    = 0x02283200
0x82CD -> R0=0x022831C0, data=95599559 95599559, slot0=1, slot1=FFFFFFFF
0x82DF -> R0=0x02283140, data=C77CC77C C77CC77C, miss=1/82DF/0/0x40
0x82A2 -> R0=0x02283260, data=73377337 73377337, slot0=1, slot1=0
0x82C6 -> R0=0x022831C0, data=95599559 95599559, slot0=1, slot1=0
```

当前判断更新：
- 双 slot 可以消除上一版在 chunk0/chunk1 间来回失效的抖动。
- `82DF` miss 后 chunk0 被装入 slot1，slot0 的 chunk1 仍保留并可被 `82C6` 命中。
- 当前 probe 只接管 `R2=0x40` 的 1x2 路径；正式版还需要把 1x1、多 chunk 替换策略和代码区布局一起纳入设计。
