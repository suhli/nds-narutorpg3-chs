# 菜单文本批量翻译与回写备忘

## 当前结论

- 标题菜单中文已经能显示，说明 overlay 菜单文本写回、中文码点编码、1x2 字形渲染链路可以打通。
- 之前方块字不是“字模完全没生成”，而是原来的延迟动态缓存不适合标题菜单这种首次绘制后不立刻重绘的场景。
- 当前可工作的 ROM 使用的是 `immediate_copy_on_1x2_miss_probe`：在 1x2 字形 miss 时同步拷贝源页，保证第一次绘制就能拿到字形。
- 这个字体补丁仍是探针性质：1x2 路径已验证标题菜单有效，1x1 同步 miss 路径还没有正式收敛，后续不能直接把它命名为最终版。

## 扫描范围与数量

扫描脚本：

```text
tools/scan_menu_overlay_strings.py
```

扫描输出：

```text
text/menu/overlay_menu_candidates.tsv
text/menu/overlay_menu_scan_report.json
```

当前高置信扫描结果：

```text
candidate_count=346
arm9=16
overlay_0000=78
overlay_0001=48
overlay_0002=5
overlay_0003=167
overlay_0004=17
overlay_0005=15
```

正式批量处理只选连续菜单/提示表区，不把所有扫描结果直接写回：

```text
overlay_0000 offset >= 0x2F6AC
overlay_0001 offset >= 0x1EC60
overlay_0002 offset >= 0x128B8
overlay_0003 offset >= 0x42A60
overlay_0004 offset >= 0x5270
```

本轮进入批量菜单表的记录：

```text
selected_rows=278
unique_keys=206
ready=278
missing_font_chars=0
```

## 翻译表约定

翻译准备脚本：

```text
tools/prepare_overlay_menu_translations.py
```

翻译输出：

```text
text/menu/overlay_menu_translations.tsv
text/menu/overlay_menu_translation_report.json
```

关键字段含义：

```text
id              稳定记录 ID，含 component 和 offset
component       arm9 或 overlay_000x
source_file     回写目标相对路径
offset          文件内偏移
raw_len         原始可见文本字节数，不含 00
slot_len        固定槽长度，含尾部 00 padding
raw_hex         原始可见文本 bytes
jp_text         原始日文文本
jp_key          去掉首尾全角/半角空格后的翻译 key
zh_text         中文译文，不手工补尾部空格
encoded_hex     按当前码表编码后的写回 bytes
status          ready 才允许写回
```

翻译策略：

- 按 `jp_key` 去重翻译，同一日文短语复用同一译文。
- 优先使用大陆常见译名和当前正文术语：鸣人、佐助、小樱、卡卡西、查克拉、忍术、通灵、写轮眼、白眼等。
- 菜单项优先短译，适配固定槽容量，例如 `はじめから -> 开始`、`つづきから -> 继续`、`ファイルさくじょ -> 删除存档`。
- `%s`、数字、`／`、`：`、`？` 这类格式符和 UI 符号必须保留语义；不要把 `%s` 改成中文占位符。
- 不默认保留原文首尾空格；普通菜单项由写回脚本零填充固定槽。多列排版字符串才在译文中保留必要全角空格。
- 当前 278 条均为本地菜单词典译文，属于可运行草稿；仍需要按实际画面校对布局、换行、语气和术语。

## 编码与字体规则

- 菜单回写不混入正文 `frozen_translation.tsv`，单独维护 `text/menu/overlay_menu_translations.tsv`。
- 中文字符优先查 `text/code_table/zh_code_table.tsv`，按 big-endian 写入两字节码点。
- CP932 可编码的 ASCII、全角数字、全角符号、`%s` 等按原 CP932/ASCII 字节写入。
- 回写前必须确认 `status=ready`：无超长、无缺字、无缺码表。
- 如果后续翻译引入新汉字，不能只写 overlay；需要追加菜单扩展码表并重建字体文件，否则会再次显示方块。
- 当前菜单译文已检查：`missing_font_chars=""`，暂不需要扩展字库。

## 回写与测试 ROM

构建脚本：

```text
tools/build_full_writeback_menu_overlay_rom.py
```

本轮测试 ROM：

```text
rom/narutorpg3_chs_full_writeback_menu_v1.nds
rom/unpacked/narutorpg3_chs_full_writeback_menu_v1/
plan/cache/text-writeback-smoke/full-writeback-menu-v1-records.json
```

写入内容：

```text
text_writeback_rows=5863
menu_writeback_rows=278
font_cache_strategy=immediate_copy_on_1x2_miss_probe
```

`ndstool -i` 校验结果：Header CRC OK，Banner CRC OK。

## 后续 QA 顺序

1. 标题菜单：开始、继续、删除存档、Wi-Fi 设置、分发好友、声音测试。
2. 声音测试菜单：BGM、角色、语音、停止、播放、返回提示。
3. 存档流程：无数据、损坏数据、文件名、存档开始是否能进入。
4. 战斗菜单：攻击、忍术、道具、替换、防御、逃跑、查克拉不足、术封印提示。
5. 道具/装备/状态菜单：体力、查克拉、攻击、防御、速度、忍力、装备状态、多列排版。
6. Wi-Fi/好友菜单：好友代码、对战设置、成绩、名字设置、点数等。

可见画面验证优先用 Windows 窗口截图；MCP 继续用于内存、寄存器和断点。之前 MCP 截图曾连到非可见 DeSmuME 实例，后续不要只凭 MCP 截图判断 UI。

## 待收敛事项

- 把 1x2 即时 miss 探针整理成正式动态字体缓存补丁，并补齐 1x1 同步 miss 路径。
- 对 `text/menu/overlay_menu_candidates.tsv` 中未进入处理块的候选做二次分类：真实隐藏菜单、误识别二进制碎片、暂不处理。
- 对 206 个唯一菜单译文做人工校对，尤其是角色名、通灵兽名、战斗状态语气和多列字符串。
- 如果后续继续扩大菜单范围，优先走“扫描 -> 去重 key -> 翻译表 -> 编码/字体检查 -> 固定槽写回 -> 模拟器验证”的闭环，不要手工零散 patch。
