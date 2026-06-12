# v29 message 变长终止符压缩候选

## 结论

如果不再要求 message 记录对齐原文长度，可以把普通 `03 00` 终止符移动到译文后面，并删除中间的全角空格填充。这能直接消除短译文后 `81 40` 被解释器继续消耗造成的空白显示或空白等待。

该策略已经实现为显式开关 `--compact-message-terminators`，默认仍关闭。

## 手测结果

用户手测 v29 后反馈：所有对话都卡死。该结果否定了“直接缩短 message 文件”的方向。

后续不要把该策略升级为默认；如需继续解决空白问题，应保持原始槽位长度。v30 已改为 `03 00` 提前、后面用全角空格补齐原文长度。

## 适用范围

只适用于普通 message 记录：

- 原记录以 `03 00` 作为结束符。
- 译文后到原始结束符之间只有为了补齐槽位写入的 `81 40` 全角空格。
- 记录没有固定 `CTRL_0000` 子槽位边界。
- 记录不是参数表、菜单固定布局、NUL4 描述表或 overlay 模板。

不适用：

- 固定布局文本。
- `CTRL_0000` 合并子槽位。
- 依赖原始宽度的 overlay 字段。
- 原始尾部不是普通 `03 00` 的特殊消息。

## 写回方式

固定槽位策略：

```text
prefix + encoded_text + 81 40 padding + 03 00
```

v29 压缩策略：

```text
prefix + encoded_text + 03 00
```

因为长度会变短，写回器必须按文件重建，而不能只在原 offset 原地覆盖。每个目标文件按原始记录 offset 顺序写入，删除 padding 后，后续记录的输出 offset 会随之提前。

## 风险判断

这是一条比 v28 更激进的候选方案。它保留了每条消息流自己的 `03 00` 终止符，但不再保留原文件内后续数据的原始物理 offset。

风险点：

- 如果脚本解释器只顺序读取到 `03 00`，该方案更干净。
- 如果同文件内存在跳转表或绝对 offset 引用，后续内容前移可能导致运行时跳转错误。

因此该策略不能仅凭静态字节核对直接升级为默认，需要用用户手测覆盖剧情连续对白、NPC 对话、菜单说明和存档/商店流程。

## 当前候选

```text
rom/narutorpg3_chs_patcher_v29_compact_msg_terminators.nds
SHA256 54187C15CF32A6E872614FB61DA6006D012E870B9622683426E6FC04DE70DEA6
```

静态结果：

```text
affected_file_count=246
compacted_row_count=3055
compacted_removed_bytes=70312
text_mismatch_count=0
structural_risk_rows=0
ndstool=Header CRC OK / Banner CRC OK
```

本轮未使用 DeSmuME/MCP。
