# Stage 1: 编码预览与容量风险扫描

更新时间：2026-06-02

## 状态

已完成。

## 输入

```text
text/code_table/frozen_translation.tsv
text/code_table/zh_code_table.tsv
```

## 目标产物

```text
tools/encode_translation_text.py
text/writeback/encoded_preview.tsv
text/reports/writeback-capacity-report.json
```

## 当前约束

- 不修改 ROM。
- 不打包 ROM。
- 不覆盖 `rom/origin.nds`。
- 中文码点端序、控制符恢复、ASCII 策略和 padding 策略必须显式出现在预览或报告中。

## 执行记录

已实现并运行：

```text
tools/encode_translation_text.py
```

生成：

```text
text/writeback/encoded_preview.tsv
text/reports/writeback-capacity-report.json
```

## 扫描摘要

- 总行数：5863。
- 候选编码完整行数：5863。
- 容量已知行数：5863。
- 固定 payload 容量超限：0。
- 缺码表字符：0。
- Stage 2 立即可写样本：0。
- 仅剩端序风险的候选：414。

风险计数：

```text
endian_unverified=5852
needs_ascii_policy=590
padding_ambiguous=5432
```

固定槽状态计数：

```text
blocked_ascii_policy=590
blocked_padding_policy=4859
candidate_fixed_slot_pending_endian=414
```

控制符候选恢复：

```text
candidate_little_endian_raw_hex_supported=1998
not_applicable=3865
```

## 关键结论

- 普通可见中文和全角符号均可从 `zh_code_table.tsv` 得到候选编码。
- 当前候选中文码点按 big-endian 输出，例如 `0xF040 -> F0 40`，但这只是根据 CP932 原始文本字节顺序做的候选，尚未有运行时验证。
- Stage 2 预检发现原 `0xF000..0xF7C1` 连续分配存在非法 SJIS trail 风险，已修正为 `0xF040..0xFAAB` SJIS 形状分配；当前报告 `code_byte_shape.verdict=sjis_shape_ok`。
- `{CTRL_xxxx}` 候选按 little-endian u16 输出；含控制符的 1998 行都能在 `raw_hex` 中找到支持该候选的字节出现证据。
- `source_byte_len` 记录原始记录长度；原始记录尾部通常包含 `03 00` 终止符。固定槽 payload 容量需要扣除终止符，因此预览新增 `payload_capacity` 字段。
- 行尾 ASCII padding 被剥离为候选 payload 之外的独立风险，保留 `padding_spaces` 记录，不作为普通可见文本静默编码。

## 下一步门槛

Stage 2 写回样本前必须先解决：

- 中文扩展码 `0xF040..0xFAAB` 的实际文本读取端序。
- 普通 ASCII 策略。
- 尾部 padding 策略。

在端序未验证前，报告中的 414 行只能视作 `candidate_fixed_slot_pending_endian`，不能直接写回。
