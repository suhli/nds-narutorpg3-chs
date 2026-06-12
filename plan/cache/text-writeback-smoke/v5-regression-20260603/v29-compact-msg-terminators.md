# v29 message 终止符压缩候选

## 背景

v28 已确认 `{CTRL_0001}` 在普通对白中可以是正常换行，不能全量删除。用户继续提出另一种方向：如果不再强制对齐原文槽位长度，只保留一个 `03 00` 终止符，是否可以消除短译文后的全角空格填充。

本轮按这个方向实现为显式候选开关，没有改变默认 v28 写回策略。

## 实现策略

新增参数：

```text
--compact-message-terminators
```

启用后，仅对满足以下条件的文本记录做变长压缩：

- 普通 message 记录。
- 当前策略为 `fullwidth_space_fill_before_original_terminator`。
- 终止符为普通 `03 00`。
- 不是固定 `CTRL_0000` 子槽位记录。
- 不是 overlay 模板、参数表、NUL4 表或其他固定布局记录。

压缩方式：

```text
原策略: prefix + encoded_text + fullwidth_padding + 03 00
新策略: prefix + encoded_text + 03 00
```

写回器不再逐条原地覆盖这些记录，而是按目标文件分组、按原始 offset 顺序重建文件内容。每条后续记录的 `output_offset` 会随前面删除的 padding 自动前移。

默认不带该参数时，仍保持 v28 的固定长度原位写回。

## 影响范围

静态统计：

```text
affected_file_count=246
compacted_row_count=3055
compacted_removed_bytes=70312
```

示例记录：

```text
id=zh_txt_dc122c8a_000DAA_0047
source_file=msg/fld/029.m
original_offset=0xDAA
output_offset=0x86A
source_len=106
compact_len=48
removed_len=58
```

该记录尾部已从：

```text
... encoded_text + 58 bytes 81 40 padding + 03 00
```

变为：

```text
... encoded_text + 03 00
```

`03 00` 后面紧接原始文件中下一段脚本或消息字节，不再保留可见全角空格填充。

## 候选 ROM

```text
rom/narutorpg3_chs_patcher_v29_compact_msg_terminators.nds
SHA256 54187C15CF32A6E872614FB61DA6006D012E870B9622683426E6FC04DE70DEA6
```

构建记录：

```text
patcher/work/build_20260611_230031/patcher-build-summary.json
plan/cache/text-writeback-smoke/v5-regression-20260603/v29-compact-msg-terminators-records.json
```

## 静态验证

- 文本记录写回核对 `text_mismatch_count=0`。
- 压缩记录核对 `compacted_row_count=3055`、`compacted_removed_bytes=70312`。
- 结构审计 `risk_rows=0`。
- `ndstool -i`：Header CRC OK / Banner CRC OK。
- 文本和菜单缺字为 0，字体仅保留既有占位字符 `U+E0FD`。
- 本轮未使用 DeSmuME/MCP，运行时验证继续由用户手动完成。

验证文件：

```text
plan/cache/text-writeback-smoke/v5-regression-20260603/v29-compact-msg-terminators-byte-compare.json
plan/cache/text-writeback-smoke/v5-regression-20260603/v29-compact-msg-terminators-structural-audit.json
plan/cache/text-writeback-smoke/v5-regression-20260603/v29-compact-msg-terminators-structural-audit.tsv
```

## 风险

该方案不再保持原始文件长度，因此会改变 246 个 message 文件内后续字节的物理 offset。静态核对能证明译文、控制符和终止符写入符合当前规则，但不能完全证明运行时代码或脚本没有依赖同文件内部绝对 offset。

需要重点手测：

- `zh_txt_dc122c8a_000DAA_0047` 甜栗对白是否仍正常两行显示且无空白等待。
- 剧情连续对白是否出现跳段、自动结束或颜色继承异常。
- 存档、商店、道具说明、菜单说明等之前受 padding 影响的页面是否消除空白页。
- 长剧情场景中后续 NPC 和事件是否仍能触发，排除同文件 offset 前移带来的脚本跳转问题。

