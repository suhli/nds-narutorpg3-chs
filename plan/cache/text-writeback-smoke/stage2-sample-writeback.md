# Stage 2: 端序验证与低风险固定槽样本回写

更新时间：2026-06-02

## 状态

已完成。

## 当前门槛

Stage 1 没有发现超长或缺码表问题，但所有中文扩展码行仍带有 `endian_unverified` 风险。因此 Stage 2 的第一步不是写 ROM，而是验证 `0xF040..0xFAAB` 在文本字节流中的端序。

本阶段已先修正码表字节形状：原 `0xF000..0xF7C1` 连续分配包含非法 SJIS trail 和低字节 `00` 风险，已改为 `0xF040..0xFAAB` SJIS 形状分配，`0xFA40` 因 raw word 冲突被跳过。

## 可用输入

```text
text/writeback/encoded_preview.tsv
text/reports/writeback-capacity-report.json
plan/cache/text-writeback-smoke/font-build-smoke-sjis-code-table/
```

## 候选样本池

`writeback-capacity-report.json` 中 `examples.pre_endian_candidates` 提供了只剩端序风险的候选。当前数量为 414 行。

前 5 个候选：

```text
msg/eiga/015.m offset=0x250 encoded_len=8 payload_capacity=10
msg/eiga/022.m offset=0x1A6 encoded_len=20 payload_capacity=28
msg/eiga/024.m offset=0x1A encoded_len=24 payload_capacity=34
msg/eiga/027.m offset=0x166 encoded_len=12 payload_capacity=16
msg/eiga/039.m offset=0x1A encoded_len=20 payload_capacity=28
```

## 已执行

### 码表字节形状修复

重新运行：

```text
.\.venv\Scripts\python.exe -B tools\extract_translation_charset.py --start-code 0xF040 --code-shape sjis
```

结果：

```text
entries=1986
range=0xF040..0xFAAB
code_shape=sjis
collision_count=0
skipped_code_count=1
skipped_code=0xFA40 raw_text_word
sjis_shape_invalid=0
low_byte_zero=0
```

### 编码预览刷新

重新运行：

```text
.\.venv\Scripts\python.exe tools\encode_translation_text.py
```

结果：

```text
row_count=5863
encoded_complete_count=5863
overflow_count=0
stage2_eligible_count=0
pre_endian_candidate_count=414
code_byte_shape.verdict=sjis_shape_ok
```

### font-dir 重新构建

重新运行：

```text
.\.venv\Scripts\python.exe -B tools\build_vram_font_files.py --manifest text\code_table\font_manifest.json --output-dir plan\cache\code-table-extraction\font-build-smoke
.\.venv\Scripts\python.exe -B tools\build_vram_font_files.py --manifest text\code_table\font_manifest.json --output-dir plan\cache\text-writeback-smoke\font-build-smoke-sjis-code-table
```

结果：

```text
entries=1986
1x1_source_pages=993
1x2_source_pages=993
chs_1x1.map size=0x7C40
chs_1x2.map size=0x7C40
map_first=0xF040
map_last=0xFAAB
```

## 待执行

- DeSmuME MCP 显示验证。
- 如果显示失败，优先判断是中文扩展码端序、文本解析、动态字体缓存还是样本可达性问题。
- 不覆盖 `rom/origin.nds`。

## 样本写入

构建脚本：

```text
tools/build_text_writeback_smoke_rom.py
```

运行：

```text
.\.venv\Scripts\python.exe -B tools\build_text_writeback_smoke_rom.py
```

输出：

```text
work=rom/unpacked/text_writeback_smoke_build_20260602_180705
output=rom/text_writeback_smoke.nds
records=plan/cache/text-writeback-smoke/sample-writeback-records.json
samples=2
```

样本：

```text
msg/fld/013.m offset=0xAE
jp=「こちらは　びょうしつです　おみまいですか？」
zh=「这里是病房，您是来探病的吗？」
write=encoded_payload + 03 00 + zero_fill(14)

param/item_data.dat offset=0x3C60
jp=ナルトカード
zh=鸣人卡片
write=encoded_payload + zero_fill(4)
```

样本记录：

```text
plan/cache/text-writeback-smoke/sample-writeback-records.json
```
