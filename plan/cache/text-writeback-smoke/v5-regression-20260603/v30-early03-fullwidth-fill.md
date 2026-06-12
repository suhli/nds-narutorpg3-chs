# v30 固定长度早停 03 + 全角填充候选

## 背景

用户手测 v29 后反馈：变长压缩候选会导致所有对话卡死。该结果说明 message 文件或解释流程很可能依赖原始槽位长度、后续 offset 或固定步进，不能直接删除 `03 00` 前的 padding 并缩短文件。

本轮按用户提出的新方向实现：保持原始槽位长度不变，把普通 `03 00` 提前放到译文后面，再用全角空格填充到原文长度。

## 写回策略

新增参数：

```text
--early-message-terminator-fullwidth-fill
```

启用后，仅对原本会使用 `fullwidth_space_fill_before_original_terminator` 的普通 message 记录生效：

```text
v28 默认: prefix + encoded_text + 81 40 padding + 03 00
v29 变长: prefix + encoded_text + 03 00
v30 候选: prefix + encoded_text + 03 00 + 81 40 padding
```

约束：

- 目标文件长度和每条记录源槽位长度保持不变。
- 不移动后续记录的物理 offset。
- 不作用于固定 `CTRL_0000` 子槽位。
- 不作用于 NUL4 描述表、参数表、overlay 固定布局或特殊 scene-tail message。
- `--compact-message-terminators` 和 `--early-message-terminator-fullwidth-fill` 互斥。

## 候选 ROM

```text
rom/narutorpg3_chs_patcher_v30_early03_fullwidth_fill.nds
SHA256 F5132D5B3482B4BA03F0DB779326C1115E50914F8DCAC98335D8C638A20210A9
```

构建记录：

```text
patcher/work/build_20260612_101420/patcher-build-summary.json
plan/cache/text-writeback-smoke/v5-regression-20260603/v30-early03-fullwidth-fill-records.json
```

## 静态验证

- 文本记录写回核对 `text_mismatch_count=0`。
- 普通 message 早停覆盖 `early_03_fullwidth_fill_row_count=3072`。
- 后置全角填充总量 `early_03_fullwidth_fill_bytes=70312`。
- 文件没有压缩：`compacted_row_count=0`、`compacted_removed_bytes=0`。
- 结构审计 `risk_rows=0`。
- `ndstool -i`：Header CRC OK / Banner CRC OK。
- 文本和菜单缺字为 0，字体仅保留既有占位字符 `U+E0FD`。
- 本轮未使用 DeSmuME/MCP，运行时验证继续由用户手动完成。

验证文件：

```text
plan/cache/text-writeback-smoke/v5-regression-20260603/v30-early03-fullwidth-fill-byte-compare.json
plan/cache/text-writeback-smoke/v5-regression-20260603/v30-early03-fullwidth-fill-structural-audit.json
plan/cache/text-writeback-smoke/v5-regression-20260603/v30-early03-fullwidth-fill-structural-audit.tsv
```

## 示例核对

目标记录：

```text
id=zh_txt_dc122c8a_000DAA_0047
source_file=msg/fld/029.m
offset=0xDAA
source_len=106
encoded_len=46
```

v30 实际写入：

```text
terminator_actual_offset_in_record=46
post_terminator_len=58
post_terminator_all_fullwidth_pairs=true
```

也就是该条变为：

```text
译文 46 bytes + 03 00 + 58 bytes 全角空格
```

## 风险

该候选避免了 v29 的变长/offset 风险，但仍有一个运行时假设：解释器遇到提前的 `03 00` 后，会按固定槽位或上层结构跳过后置 padding，而不是继续把 `03 00` 后的全角空格当成下一段脚本解释。

如果 v30 仍然卡死，说明不能在普通剧情 message 中提前 `03 00`；下一步应转向寻找“不可见但可安全消耗”的填充控制序列，而不是移动终止符。

