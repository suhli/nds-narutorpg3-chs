# v33 事件脚本 message 零填充排除规则

## 结论

`msg/fld/evt/*.m` 不是普通固定槽文本表。它们是事件脚本中的对白消息，文本记录前缀混有事件对白头。对这类记录提前写入 `03 00` 后，如果用 `00` 填充剩余槽位，运行时会把这些 `00` 纳入事件流解释，导致连续对白被跳过。

因此，零填充早停策略不能用于 `msg/fld/evt/`。

## 规则

普通 message 零填充早停：

```text
译文 + 03 00 + 00 padding
```

适用范围必须排除：

```text
msg/fld/evt/
```

事件脚本 message 继续保留原始 `03 00` 位置：

```text
译文 + padding + 原位置 03 00
```

## 验证

- v33 候选：`rom/narutorpg3_chs_patcher_v33_evt_no_zero_fill.nds`
- SHA256：`33047C77BAF350B393D8156A63571A0DE7D13DFBBED833F7E752E49086B00A38`
- `msg/fld/evt` 事件脚本消息：1389 条。
- 事件脚本消息中早停零填充：0 条。
- 用户指出的 `msg/fld/evt/000.m:0x1DE..0x358` 7 条目标记录均恢复到原始 `03 00` 末尾位置。
- `ndstool -i`：Header CRC OK / Banner CRC OK。

未使用 DeSmuME/MCP，运行时验证继续由用户手动完成。
