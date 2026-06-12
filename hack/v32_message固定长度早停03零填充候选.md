# v32 message 固定长度早停 03 零填充候选

## 结论

message 文件不能采用 v29 的变长压缩；运行时很可能依赖文件内后续记录 offset。v32 继续保持原始文件长度和记录槽位长度，只把普通 `03 00` message 改为：

```text
译文 + 03 00 + 00 padding
```

这和 v30 的差异是 padding 字节从全角空格 `81 40` 改为 `00`。

## 适用范围

只适用于普通 `03 00` 结尾的 message 记录。

不适用于：

- 固定 `CTRL_0000` 子槽位记录。
- NUL4 描述表。
- 参数表。
- overlay 固定布局。
- 特殊 scene-tail message。

## 控制符风险

`03 00` 既可能是普通 message 结束符，也可能来自原始控制序列中的 `{CTRL_0003}`。因此审计规则不能要求 replacement 内完全没有内部 `03 00`，而是要求 replacement 不得比 raw 新增内部 `03 00`。

`{CTRL_0001}` 虽然通常表现为换页/换行，但在 `{CTRL_0300}{CTRL_0001}{CTRL_8200}` 这类序列中也承担结构分隔作用。如果删除它会把相邻控制符拼成新的裸字节 `03 00`，应保留它。

## 验证记录

- 候选 ROM：`rom/narutorpg3_chs_patcher_v32_early03_zero_fill.nds`
- SHA256：`EFC2B8A27B1213FA5189BC159C006822BA35D3AA03DB184A543776BA188996EF`
- 早停零填充行：3179。
- 早停零填充字节：70348。
- 结构审计：`risk_rows=0`。
- 实际字节审计：`risk_count=0`。
- `ndstool -i`：Header CRC OK / Banner CRC OK。

未使用 DeSmuME/MCP，运行时验证继续由用户手动完成。
