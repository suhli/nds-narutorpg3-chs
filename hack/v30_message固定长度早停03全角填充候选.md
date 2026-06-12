# v30 message 固定长度早停 03 全角填充候选

## 运行反馈修正

v29 的变长压缩方案在用户手测中导致所有对话卡死。该反馈说明普通 message 文件不能直接缩短：即使每条消息保留了自己的 `03 00`，删除 padding 后改变后续 offset 也会破坏运行时流程。

因此 v29 变长压缩只能保留为失败候选，不应作为默认策略。

## v30 策略

v30 改为固定长度：

```text
prefix + encoded_text + 03 00 + 81 40 padding
```

目标：

- 让文本解释器尽早看到 `03 00`，避免继续显示短译文后的空格。
- 保持原始记录长度和文件内后续 offset 不变，避免 v29 的卡死问题。

该策略由显式参数启用：

```text
--early-message-terminator-fullwidth-fill
```

默认构建不启用该策略。

## 适用范围

仅适用于普通 `03 00` message，并且必须满足：

- 原策略是 `fullwidth_space_fill_before_original_terminator`。
- 不是固定 `CTRL_0000` 子槽位。
- 不是 NUL4 描述表。
- 不是 overlay 或参数表固定布局。
- 不是特殊 scene-tail message。

## 当前候选

```text
rom/narutorpg3_chs_patcher_v30_early03_fullwidth_fill.nds
SHA256 F5132D5B3482B4BA03F0DB779326C1115E50914F8DCAC98335D8C638A20210A9
```

静态结果：

```text
early_03_fullwidth_fill_row_count=3072
early_03_fullwidth_fill_bytes=70312
text_mismatch_count=0
structural_risk_rows=0
ndstool=Header CRC OK / Banner CRC OK
```

本轮未使用 DeSmuME/MCP。

