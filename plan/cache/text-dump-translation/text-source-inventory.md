# 文本来源盘点

## 阶段目标

本阶段只建立候选文本来源清单和下一步处理方式，不直接翻译、不生成码表、不回写 ROM。

需要为后续 dump 保留足够定位信息：来源文件、偏移、记录序号、指针引用、压缩状态、原始字节、编码猜测、控制符风险和边界规则。

## 输入范围

- `rom/origin.nds`
- `rom/unpacked/origin/`
- `rom/unpacked/origin/data/text/`
- `rom/unpacked/origin/overlay/`
- `hack/`
- `plan/vram-font-bypass.md`

## 已知候选目录

### 明显文本目录

`rom/unpacked/origin/data/text/` 下当前顶层目录：

```text
cutin2script
msg
param
script
```

该目录内文件扩展名计数：

```text
.m    299
.s    208
.msg   39
.bin   28
.dat   19
.scr    2
```

初步优先级：

- `data/text/msg/`：优先检查。文件名和扩展名显示它很可能包含对白、战斗消息、系统消息或菜单消息。
- `data/text/script/`：优先检查。需要确认 `.s/.scr` 是脚本指令、文本引用、控制流，还是混合文本。
- `data/text/param/`：中优先级。可能包含道具、技能、角色、菜单参数或短文本。
- `data/text/cutin2script/`：中优先级。文件小而集中，可能是 cut-in 或演出脚本，需要结构确认。

### 全 data 层候选

`rom/unpacked/origin/data/` 中还存在大量非 `data/text/` 资源，扩展名计数包括：

```text
.p    986
.t    926
.n    806
.s    606
.m    497
.c    282
.tt   150
.tp   150
.bin   41
.msg   39
.dat   19
.scr    3
.tbl    2
```

处理原则：

- 先从 `data/text/` 建立已确认格式。
- 再用已确认编码和控制符模型扫描其他 `.m/.s/.msg/.dat/.bin` 来源。
- `.tbl` 当前优先作为字体编码映射参考，不当作文本来源直接翻译。

### overlay 候选

`rom/unpacked/origin/overlay/` 有 6 个 overlay：

```text
overlay_0000.bin 198752
overlay_0001.bin 127680
overlay_0002.bin  77952
overlay_0003.bin 284608
overlay_0004.bin  21504
overlay_0005.bin 177152
```

overlay 初期只做只读扫描：

- 搜索 NitroFS 路径引用、消息表引用、指针表、硬编码菜单短句。
- 不把 overlay 二进制中的疑似日文直接混入正式翻译表，除非能确认边界和引用方式。

## 盘点字段

后续 inventory 表建议包含：

```text
source_file
source_kind
extension
size
source_sha1
record_count_guess
compression
encoding_guess
boundary_rule
pointer_ref
priority
next_action
notes
```

## 第一批检查项

1. 抽样 `data/text/msg/**/*.m` 和 `data/text/msg/**/*.msg`，确认头部、记录表、结束符和控制符。
2. 抽样 `data/text/script/**/*.s` 和 `data/text/script/**/*.scr`，确认脚本是否直接嵌入文本，或只引用 `msg` 记录。
3. 对比 `data/text/msg` 与 `data/text/script` 的同名编号，判断脚本和消息是否成对。
4. 用字体 `.tbl` 的已知编码范围辅助判断文本编码，但不把字体表改造成中文码表。
5. 扫描 overlay 中的 `data/text` 路径、消息文件名和疑似指针表引用。
6. 记录每个候选来源是否需要解压、结构分析、运行时确认或暂不处理。

## 待确认问题

- `.m/.msg` 是否共用同一种记录结构。
- `.s/.scr` 是脚本控制流、文本容器，还是消息引用表。
- 文本编码是否直接对应字体 `.tbl` 字符码。
- 控制符、换行、等待、变量、名字和颜色等标记的字节形式。
- 每条文本的硬边界来自长度字段、指针表、结束符，还是脚本结构。
- 是否存在压缩文本资源。
- 菜单、道具、技能、人物名是否在 `data/text/param/`，还是散落在其他 `data/` 资源。

## 当前结论

第一批 dump 应从 `data/text/msg/` 和 `data/text/script/` 开始。翻译阶段只能消费已经确认边界和控制符的条目；未确认来源先进入 TODO/疑似清单。

2026-05-29 初始执行结果：

- `data/text/msg/` 已确认可直接按 CP932/SJIS 抽取，并能保留常见 `{CTRL_xxxx}` 控制词。
- `data/text/param/` 中也存在 CP932/SJIS 名称、术、道具和说明文本，当前先作为候选导出，后续需要结构边界建模。
- `data/text/script/` 抽样更像脚本指令/指针结构，本轮没有作为正式文本来源直接导出。
- 初始候选输出见 `text/original/jp_dump.tsv` 和 `text/translation/zh_translation.tsv`，摘要见 `plan/cache/text-dump-translation/dump-results.md`。
