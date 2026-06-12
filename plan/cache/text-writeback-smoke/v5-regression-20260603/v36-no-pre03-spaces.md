# v36 终结符前填充清理

## 背景

用户手测确认 v33 已不再漏掉连续事件对白，但底部对白框出现额外空白行。静态复查显示 v33 没有“填充后再次出现 `03 00`”的双终结符结构；真正的空白来源是大量记录仍保持 `译文 + 全角空格 padding + 03 00`，渲染器会把终结符前的 `81 40` 当作可见文本推进。

本轮未使用 DeSmuME/MCP；运行时验证继续由用户手动完成。

## 规则变更

- 非事件普通 `03 00` message：沿用 v33 的 `译文 + 03 00 + 00 padding`。
- `msg/fld/evt/` 事件脚本 message：改为 `译文 + 03 00 + 全角空格 padding`，避免 v32 的事件流跳过风险。
- 固定控制位记录：内部控制符和分段偏移保持原位，只把最后一段文本后的最终 `03 00` 提前，尾部用全角空格补齐。
- 固定 `CTRL_0000` 子槽位记录：内部 `00 00` 分隔符保持原位，只把最后一个子槽后的最终 `03 00` 提前，尾部用全角空格补齐。

新增开关：

```text
--event-script-early-message-terminator-fullwidth-fill
--control-slot-final-message-terminator-fullwidth-fill
```

v36 构建命令组合：

```text
--early-message-terminator-zero-fill
--event-script-early-message-terminator-fullwidth-fill
--control-slot-final-message-terminator-fullwidth-fill
```

## 候选 ROM

```text
rom/narutorpg3_chs_patcher_v36_no_pre03_spaces.nds
SHA256 B29FEA1B5B7BBD5E2010BD5AF1262676B6B71CB1D6E126847BECCB9A71954BB9
build_dir patcher/work/build_20260612_154954
```

`ndstool -i` 结果：Header CRC OK，Banner CRC OK。

## 静态验证

结构审计：

```text
plan/cache/text-writeback-smoke/v5-regression-20260603/v36-no-pre03-spaces-structural-audit.json
risk_rows=0
```

实际写入字节扫描：

```text
plan/cache/text-writeback-smoke/v5-regression-20260603/v36-terminator-padding-audit.json
checked=5858
message_0300_rows=3236
terminator_then_zero_then_later_0300_rows=0
terminator_then_fullwidth_then_later_0300_rows=0
fullwidth_padding_before_final_0300_rows=0
zero_padding_before_final_0300_rows=0
evt_fullwidth_padding_before_final_0300_rows=0
evt_zero_tail_after_first_0300_rows=0
```

策略覆盖：

```text
early_03_zero_fill_after_terminator=1816
event_script_early_03_fullwidth_fill_after_terminator=1363
event_script_fixed_control_final_03_fullwidth_fill_after_terminator=3
fixed_control_final_03_fullwidth_fill_after_terminator=1
fixed_subslot_final_03_fullwidth_fill_after_terminator=52
```

剩余 3 条 `multi_0300`：

```text
zh_txt_0d5c73a4_000484_0016 msg/fld/011.m 0x484
zh_txt_0d5c73a4_00058A_0019 msg/fld/011.m 0x58A
zh_txt_31fd479b_001354_0062 msg/fld/030.m 0x1354
```

这 3 条不是“填充后再出现终结符”模式；扫描结果中的 `between_first_last=mixed` 表明中间包含混合控制/文本字节，后续若对应运行时截图异常再单独处理。

