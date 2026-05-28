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
