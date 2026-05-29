# 文本 dump 与翻译基线

## 背景

字体方案已经推进到可作为文本阶段前置条件的 v0 闭环：

```text
TTF -> font-dir -> ROM -> 模拟器冒烟
```

已验证入口包括：

```text
tools/build_vram_font_files.py
tools/build_vram_font_dynamic_cache_rom.py
tools/run_vram_font_integrated_smoke.py
```

关键产物与证据：

```text
plan/cache/vram-font-bypass/generated-font-build.md
plan/cache/vram-font-bypass/integrated-build-and-smoke.md
rom/narutorpg3_chs_dynamic_font_v0_generated_font.nds
plan/cache/vram-font-bypass/integrated-smoke-generated-font-samples.json
```

当前字体 v0 已能从 TTF 和 manifest 生成 `chs_1x1.map/chunk`、`chs_1x2.map/chunk`，再构建 ROM 并通过模拟器集成冒烟。后续不在本计划继续扩展字体 hook、chunk 数量、字模分页或 ROM 回写逻辑。

本计划进入汉化总体节奏的第二步：dump 游戏内所有需要汉化的日文文本，并建立可审核、可冻结、可作为后续码表生成输入的翻译基线。

## 必要上下文

- 原版 ROM：`rom/origin.nds`，只读，不覆盖，不原地 patch。
- 修改 ROM 必须另行输出新文件，本计划默认不做最终文本回写 ROM。
- ROM 解包/打包流程按 `.codex/skills/ndstool-rom-workflow/SKILL.md`。
- 如需运行时确认文本来源或界面上下文，DeSmuME MCP 流程按 `.codex/skills/desmume-mcp-workflow/SKILL.md`。
- 字体 v0 作为前置完成条件保留：动态字体链路已经具备真实 TTF 字模生成和模拟器冒烟闭环。
- 本计划只产出 dump、文本格式说明、翻译表和校验工具，不进入码表生成、字模生成、文本回写或 ROM 显示验证。

## 目标

- 定位游戏内所有需要汉化的日文文本来源。
- 建立可复现 dump 工具，保留回写所需定位信息。
- 识别文本编码、控制符、结束符、换行、变量占位符和文本边界。
- 区分剧情对白、菜单、系统提示、战斗文本、道具/技能/人物名等文本类别。
- 产出稳定 ID 的原文 dump 和翻译表。
- 校验译文没有丢失控制符、变量占位符、结束符和必要结构。
- 冻结一份可供后续“码表生成与文本回写”计划使用的翻译基线。

## 非目标

- 不生成最终中文码表。
- 不生成正式中文字模 font-dir。
- 不替换原文字库或原文码表。
- 不回写文本到 ROM。
- 不构建最终汉化 ROM。
- 不做大规模模拟器显示验收。
- 不继续扩展字体 v0 的 hook、chunk table、source page 或 resident slot 机制。

后续独立计划再处理：

```text
码表生成
字模生成
原文码表替换
文本回写
ROM 构建
模拟器显示和流程验证
```

## 产物

### 工具

```text
tools/dump_text_candidates.py
tools/decode_text_assets.py
tools/check_translation_table.py
```

工具名称可在执行时按实际代码结构调整，但需要保留可复现入口。

### 数据

```text
plan/cache/text-dump-translation/text-source-inventory.md
plan/cache/text-dump-translation/encoding-control-codes.md
plan/cache/text-dump-translation/dump-results.md
plan/cache/text-dump-translation/translation-baseline.md
plan/cache/text-dump-translation/handoff-to-code-table-writeback.md
```

建议导出目录：

```text
text/original/
text/translation/
text/reports/
```

建议核心表：

```text
text/original/jp_dump.tsv
text/translation/zh_translation.tsv
text/reports/control-code-check.json
```

### 文档

- 文本来源清单：来源文件、资源类型、是否压缩、是否脚本、是否表格。
- 文本格式说明：编码、控制符、换行、结束符、变量占位符、长度/边界规则。
- 翻译表说明：字段定义、ID 规则、状态字段、校验规则。
- 后续 handoff 说明：哪些字段供码表和回写计划消费。

## 建议文本表字段

`jp_dump.tsv`：

```text
id
category
source_file
source_kind
source_sha1
offset
relative_offset
record_index
pointer_ref
length
max_length_or_boundary
compression
raw_hex
encoding
jp_text
control_tokens
terminator
boundary_confidence
context
notes
```

`zh_translation.tsv`：

```text
id
jp_id_ref
category
source_file
offset
record_index
raw_hex
jp_text
zh_text
control_tokens
status
length_risk
context_required
translator_note
qa_note
```

ID 必须稳定，不应依赖导出顺序变化。建议以来源文件、偏移和局部序号组合生成，例如：

```text
msg_<source_hash>_<offset_hex>_<index>
```

## 阶段计划

### 1. 文本来源盘点

状态：已完成初始盘点。

目标：

- 从 ROM/NitroFS 解包内容、overlay、脚本、表格和可能的压缩资源中盘点候选文本来源。
- 区分明显文本、疑似文本和非文本资源。
- 记录每类资源的路径、大小、结构线索、初步编码猜测和风险。

输入：

```text
rom/origin.nds
rom/unpacked/origin/
hack/
plan/vram-font-bypass.md
```

产物：

```text
plan/cache/text-dump-translation/text-source-inventory.md
```

完成标准：

- 有候选来源清单。
- 每个来源有下一步处理方式：直接解码、需要结构分析、需要解压、需要运行时确认或暂不处理。
- 明确第一批 dump 优先级。

### 2. 编码、控制符和边界建模

状态：进行中。

目标：

- 确认日文文本编码方式。
- 识别字符串结束符、换行、等待、变量、名字、数字、颜色或格式控制符。
- 建立控制符保留规则。
- 识别文本边界和长度限制，避免误把二进制数据 dump 成文本。

产物：

```text
plan/cache/text-dump-translation/encoding-control-codes.md
tools/decode_text_assets.py
```

完成标准：

- 至少覆盖第一批主要文本来源。
- 控制符能以稳定 token 表示，例如 `{NL}`、`{WAIT}`、`{VAR:xx}`。
- 原始字节和可读文本可以双向关联到来源偏移。
- 未确认边界和控制符的来源只能进入 TODO/疑似清单，不进入正式翻译基线。

### 3. 可复现 dump 工具与原文导出

状态：进行中。已生成候选 dump，正式回写级 dump 仍待控制符和边界模型收敛。

目标：

- 实现可复现 dump 工具。
- 为每条文本保留来源文件、偏移、原始字节、编码、类别、边界、指针引用和上下文。
- 对疑似误报、重复文本、空字符串和结构字段做标记，而不是直接删除。

产物：

```text
tools/dump_text_candidates.py
text/original/jp_dump.tsv
plan/cache/text-dump-translation/dump-results.md
```

完成标准：

- 从干净解包目录重新运行能得到稳定 dump。
- dump 结果包含所有已确认主要文本来源。
- 每条文本可以回溯到原始文件、偏移、记录序号或指针引用。
- 对未确认来源有单独 TODO，不混入已确认翻译表。

### 4. 翻译表建立与控制符校验

状态：进行中。已建立 chunk 分块、翻译 worker 规则和本地增强校验；先按 chunk 产出译文，再合并回正式翻译表。

目标：

- 基于 `jp_dump.tsv` 建立 `zh_translation.tsv`。
- 翻译可以开始，但正式翻译基线只接收已确认边界和控制符的条目。
- 校验译文保留所有必须控制符、变量占位符和结束结构。
- 标记需要上下文复核、长度风险或后续回写策略介入的条目。

产物：

```text
text/translation/zh_translation.tsv
text/translation/chunks/index.json
text/translation/chunks/source/
text/translation/chunks/translated/
text/translation/chunks/reports/
text/translation/chunks/progress.json
tools/check_translation_table.py
text/reports/control-code-check.json
plan/cache/text-dump-translation/translation-baseline.md
```

完成标准：

- 每条已确认原文都有翻译状态。
- 控制符校验通过或有明确例外说明。
- 可从译文表统计中文字符集，但本阶段不实际生成码表。
- 长文本、动态变量文本、菜单窄列文本有风险标记。
- 未确认来源只进入 TODO/疑似清单，不进入正式翻译基线。

当前执行规则：

- 分块翻译不得更新后续码表、字模或 ROM 回写产物。
- 每个 chunk 译文必须保留 `{CTRL_xxxx}` 控制符顺序；`zh_text` 序列化长度必须等于 `source_byte_len`，其中控制符 token 按原始 2 字节控制字计，其余译文按 UTF-8 字节计。
- 结构校验通过后还要做语义抽检：不能把多句教程或对白压缩成摘要，源文中的人名、称呼、条件和操作对象需要保留。
- 字节对齐不足时只在句尾补 ASCII 空格；不得使用 ASCII `?`、乱码、罗马音或空高亮 span 占位。
- 遇到“汉字术语 + 括号假名注音”时，只翻译术语，忽略注音。

### 5. 冻结 handoff 给后续码表/回写计划

状态：待开始。

目标：

- 固化本阶段输出，作为第二个 plan 的输入。
- 明确哪些文本已确认、哪些还需要运行时上下文、哪些暂不回写。
- 给后续计划提供字符集统计入口和回写定位字段。

产物：

```text
plan/cache/text-dump-translation/handoff-to-code-table-writeback.md
```

完成标准：

- `jp_dump.tsv` 和 `zh_translation.tsv` 字段稳定。
- 控制符说明和文本边界说明完整。
- 后续 plan 可以直接消费翻译表生成字符集、编码分配表和 font-dir manifest。

## 决策

- 本计划新建，不继续扩写 `vram-font-bypass`。
- 字体 v0 只作为前置依赖，不在本计划继续实现。
- dump 和翻译优先保证可追溯、可校验和可返工。
- 不在不理解控制符和边界的情况下批量替换文本。
- 第二个后续 plan 再处理码表生成、字模生成、原文码表替换、文本回写和 ROM 验证。

## 风险

- 文本可能分散在 NitroFS 文件、overlay、脚本、表格或压缩资源中。
- 编码可能不是单一表，菜单和剧情可能使用不同字库或控制符。
- 控制符如果识别不完整，翻译表会污染后续回写。
- 文本边界如果判断错误，后续回写会破坏脚本或资源结构。
- 部分文本可能需要运行时上下文才能正确翻译。
- 后续码表计划可能反向要求缩短译文或调整用字，但不应在本计划提前做编码分配。

## 当前入口

从“文本来源盘点”开始。

第一步只读检查 ROM 解包内容、overlay 和已知 `hack/` 资料，建立 `text-source-inventory.md`。不要先写回 ROM，不要生成码表，不要替换字体或原文码表。
