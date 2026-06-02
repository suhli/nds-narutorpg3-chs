# 中文码表提取计划

## 背景

`plan/text-dump-translation.md` 的范围已经明确限定为文本 dump、控制符建模、翻译表和后续 handoff，不负责码表、字模、文本回写或 ROM 验证。用户已确认翻译完成，因此本计划承接上一计划，进入中文字符集提取、编码分配和字体 manifest 生成。

上一计划原定产物 `plan/cache/text-dump-translation/handoff-to-code-table-writeback.md` 在进入本计划前缺失。本计划先补齐该 handoff，并把旧计划交接状态写清楚，再继续码表提取。

## 必要上下文

- 原版 ROM `rom/origin.nds` 只读，不覆盖、不原地 patch。
- 当前可用译文不在主表中：`text/translation/zh_translation.tsv` 有 5863 行，但 `zh_text` 全为空，不能作为码表输入。
- 当前可用译文在 `text/translation/chunks/translated/*.tsv`。
- `text/translation/chunks/index.json` 是有效 chunk 清单：`chunks=322`、`rows=5863`。
- 旧空文件 `chunk_0292.tsv`、`chunk_0293.tsv`、`chunk_0294.tsv` 不在当前 index 中，不得按 glob 误读。
- `text/translation/chunks/progress.json` 显示：`translated_chunks=322`、`validated_chunks=322`、`translated_rows=5863`、`aligned_rows=5863`、`issue_count=0`。
- 当前字体 v0 已具备 `TTF -> font-dir -> ROM -> 模拟器冒烟` 闭环。
- `tools/build_vram_font_files.py` 可从 manifest 生成 `chs_1x1.map/chunk` 和 `chs_1x2.map/chunk`，默认起始编码为 `0xE000`。
- 最新字体链路以 `hack/字体绘制链路.md` 和 `hack/字体运行时观察.md` 为准，不沿用旧的 `+0x24/+0x2C` tbl 指针误判。

## 目标

- 冻结一份可复现的已校验译文输入。
- 从冻结译文中提取中文字符集和实际可见符号。
- 忽略控制 token、结构字段和尾部 ASCII padding。
- 为字符集分配内部编码；初始假设 `0xE000` 已经冲突扫描否决。文本回写预检发现 `0xF000` 连续分配存在非法 SJIS trail 风险，最终修正为 SJIS 形状分配 `0xF040..0xFAAB`。
- 生成后续字体构建可消费的 manifest。
- 用现有字体工具完成 font-dir 构建冒烟。
- 产出后续文本回写计划可直接消费的 handoff。

## 非目标

- 不回写文本。
- 不重新打包 ROM。
- 不运行模拟器显示验证。
- 不做大规模字模视觉 QA。
- 不修改 `rom/origin.nds`。

## 产物

### 工具

```text
tools/extract_translation_charset.py
```

### 数据

```text
text/code_table/frozen_translation.tsv
text/code_table/zh_charset.txt
text/code_table/zh_code_table.tsv
text/code_table/font_manifest.json
text/code_table/font_manifest.txt
text/code_table/ignored_ascii.txt
text/reports/code-table-summary.json
```

### 计划缓存

```text
plan/cache/text-dump-translation/handoff-to-code-table-writeback.md
plan/cache/code-table-extraction/translation-input-freeze.md
plan/cache/code-table-extraction/charset-extraction.md
plan/cache/code-table-extraction/code-table-allocation.md
plan/cache/code-table-extraction/font-manifest-generation.md
plan/cache/code-table-extraction/font-build-smoke.md
plan/cache/code-table-extraction/verification.md
plan/cache/code-table-extraction/handoff-to-text-writeback.md
```

## 阶段

### Stage 0: 补齐上一计划 handoff

状态：已完成。

目标：

- 补 `plan/cache/text-dump-translation/handoff-to-code-table-writeback.md`。
- 明确旧计划 `text-dump-translation` 已交接到本计划。
- 在 `plan/state.yaml` 中切换当前计划前，避免旧计划仍悬空为未交接状态。

完成标准：

- handoff 文件记录译文输入、主表不可用状态、chunk 清单口径、控制符规则和后续风险。
- 旧计划状态在 state 中不再作为当前 in-progress 计划。

### Stage 1: 冻结译文输入

状态：已完成。

目标：

- 从 index 中列出的 322 个有效 chunk 合并出冻结 TSV。
- 后续码表、回写、QA 都使用冻结输入，避免每次隐式拼 chunk。

输入：

```text
text/translation/chunks/index.json
text/translation/chunks/progress.json
text/translation/chunks/translated/*.tsv
```

硬性规则：

- 只读取 `index.json` 中列出的 chunk。
- 不读取旧空 chunk 文件。
- 不使用 `text/translation/zh_translation.tsv` 作为码表输入。
- 每个有效 chunk 必须有非空译文，行数与 index 一致，校验报告 issue 数为 0。

产物：

```text
text/code_table/frozen_translation.tsv
plan/cache/code-table-extraction/translation-input-freeze.md
```

完成标准：

- 冻结 TSV 行数为 5863。
- 有效 chunk 数为 322。
- 输入问题数为 0。
- 缓存文档记录 chunk 清单、旧空 chunk 排除、行数和 hash。

### Stage 2: 提取字符集

状态：已完成。

目标：

- 从冻结译文的 `zh_text` 抽取可见字符集。

字符规则：

- 忽略 `{CTRL_xxxx}` 控制 token。
- 忽略行尾 ASCII padding 空格。
- 不统计结构字段、来源字段、原文字段、注释字段。
- 保留中文、中文标点、日文式标点、全角数字/字母和实际需要显示的符号。
- 普通 ASCII 单独统计到报告和 `ignored_ascii.txt`，默认不进入中文扩展码表；如后续确认某些半角符号必须替换，再显式加入。
- 字符顺序按首次出现顺序冻结，同时记录频次和首次出现位置。

产物：

```text
text/code_table/zh_charset.txt
text/code_table/ignored_ascii.txt
text/reports/code-table-summary.json
plan/cache/code-table-extraction/charset-extraction.md
```

完成标准：

- `zh_charset.txt` 非空。
- 字符集不包含控制 token 字面内容。
- 报告记录总字符数、去重字符数、控制 token 数、padding 空格数、ASCII 统计和可疑结构。

### Stage 3: 编码分配与冲突扫描

状态：已完成。

目标：

- 为字符集分配内部编码，生成后续文本回写和字体构建共享的码表。

执行结果：

- 起始编码初始尝试 `0xE000`。
- `0xE000` 方案发现 raw text word 冲突：`暴 -> 0xE34A`、`蛙 -> 0xE5B3`。
- 最终起始编码改为 `0xF040`。
- 最终编码范围为 `0xF040..0xFAAB`。
- 最终分配规则为 SJIS 形状双字节码点，跳过非法 trail 和 raw text word 冲突。
- `0xFA40` 因 raw text word 冲突被跳过。
- 每个字符分配唯一编码。
- 编码按字符首次出现顺序连续分配。
- 若冲突扫描发现风险，允许调整 `start-code` 后重新分配。

冲突扫描至少覆盖：

- 已观察控制词：`0x0000`、`0x0001`、`0x0002`、`0x0003`、`0x0103` 及翻译表中出现的其他 `{CTRL_xxxx}`。
- 原文 dump 中已出现的 16-bit 文本字节值。
- 结束符、换行、变量和高亮相关控制码。
- 已有字体 manifest / map 中的编码。
- 后续回写需保留的特殊值。

码表字段：

```text
char
unicode_hex
code_hex
modes
frequency
first_seen_chunk
first_seen_row
source_count
notes
```

`modes` 默认写 `1x1,1x2`，并在 `notes` 标为 `provisional`。正式显示模式需要后续回写/显示上下文再收窄。

产物：

```text
text/code_table/zh_code_table.tsv
plan/cache/code-table-extraction/code-table-allocation.md
```

完成标准：

- 无重复字符。
- 无重复编码。
- 冲突扫描有结果记录。
- 编码范围和最大编码写入报告。

### Stage 4: 生成字体 manifest

状态：已完成。

目标：

- 生成 `tools/build_vram_font_files.py` 可直接消费的 manifest。

JSON manifest 格式：

```json
{
  "entries": [
    {
      "code": "0xF040",
      "char": "字",
      "modes": ["1x1", "1x2"]
    }
  ]
}
```

文本 manifest 格式：

```text
0xF040 字 1x1,1x2
```

产物：

```text
text/code_table/font_manifest.json
text/code_table/font_manifest.txt
plan/cache/code-table-extraction/font-manifest-generation.md
```

完成标准：

- manifest entry 数与码表 entry 数一致，或差异有明确说明。
- 字段名为 `code`、`char`、`modes`。
- `modes` 与 `tools/build_vram_font_files.py` 的解析规则一致。

### Stage 5: font-dir 构建冒烟

状态：已完成。

目标：

- 只验证码表和 manifest 能生成字体资源，不集成 ROM。

命令：

```text
.\.venv\Scripts\python.exe -B tools\build_vram_font_files.py --manifest text\code_table\font_manifest.json --output-dir plan\cache\code-table-extraction\font-build-smoke
```

产物：

```text
plan/cache/code-table-extraction/font-build-smoke/
plan/cache/code-table-extraction/font-build-smoke.md
```

完成标准：

- 生成 `chs_1x1.map`、`chs_1x1.chunk`、`chs_1x2.map`、`chs_1x2.chunk`。
- 生成 `manifest.resolved.json`。
- 记录 `entry_count`、1x1/1x2 pages、文件大小和命令摘要。
- 明确本阶段不调用 ROM 集成脚本、不回写 ROM。

### Stage 6: 汇总与回写 handoff

状态：已完成。

目标：

- 汇总代码表提取结果，交接给后续文本编码替换和 ROM 回写计划。

产物：

```text
plan/cache/code-table-extraction/verification.md
plan/cache/code-table-extraction/handoff-to-text-writeback.md
```

完成标准：

- 后续执行者可从 `plan/state.yaml` 和 handoff 文件恢复上下文。
- handoff 包含冻结译文、字符集、码表、manifest、font-dir、编码范围、控制符规则和后续回写风险。

## 决策

- 新建 `code-table-extraction` 计划，不把上一计划扩写成码表计划。
- 先补上一计划 handoff，再进入新计划执行。
- 冻结合并 TSV 是码表提取的唯一输入。
- `zh_translation.tsv` 当前为空，禁止作为码表输入。
- 初始 `0xE000` 编码方案因 raw text word 冲突废弃；`0xF000` 连续分配又在文本回写预检中发现非法 SJIS trail 风险；最终编码范围修正为 `0xF040..0xFAAB`，按 SJIS 形状分配。
- 默认所有扩展字符先生成 `1x1,1x2` 两套字模，模式标记为 provisional。
- 本计划只到 font-dir 冒烟，不回写 ROM。

## 风险

- 如果按 glob 直接读取 chunk，旧空 chunk 可能污染统计。
- 如果直接使用空主表，会得到空字符集。
- 控制 token 未过滤会污染码表。
- ASCII padding 未过滤会污染统计。
- 半角 ASCII 是否需要新字模尚未最终确认，本计划先单独统计。
- `0xE000` 起始范围已发现冲突并废弃；后续若扩展字符集仍需重新冲突扫描。
- font-dir 构建成功不等于游戏内显示正确。
- 后续文本回写仍需处理控制符、长度限制、指针扩容和 ROM 验证。
