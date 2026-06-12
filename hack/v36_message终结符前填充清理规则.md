# v36 message 终结符前填充清理规则

## 结论

`03 00` 前的 `81 40` 全角空格会被文本渲染器当作可见文本继续排版，可能表现为底部对白框多出空白行。为了保持原文件和记录长度不变，同时避免 v29 变长压缩导致卡死，本轮采用“终结符提前、尾部填充”的固定长度策略。

## 分类规则

1. 普通非事件 `03 00` message

```text
prefix + translated_text + 03 00 + 00 padding
```

该规则不用于 `msg/fld/evt/` 事件脚本。

2. `msg/fld/evt/` 事件脚本 message

```text
prefix + translated_text + 03 00 + 81 40 padding
```

原因：v32 证明事件脚本中 `03 00` 后的 `00` padding 会影响事件流，导致连续对白跳过。

3. 固定控制位 message

内部控制符位置保持原位；只移动最后一个文本槽后的最终 `03 00`：

```text
... fixed controls ... + final_translated_text + 03 00 + 81 40 padding
```

4. 固定 `CTRL_0000` 子槽位 message

内部 `00 00` 分隔符位置保持原位；只移动最后一个子槽后的最终 `03 00`：

```text
subslot0 + 00 00 + subslot1 + ... + final_subslot_text + 03 00 + 81 40 padding
```

## v36 静态审计结果

```text
terminator_then_zero_then_later_0300_rows=0
terminator_then_fullwidth_then_later_0300_rows=0
fullwidth_padding_before_final_0300_rows=0
zero_padding_before_final_0300_rows=0
evt_zero_tail_after_first_0300_rows=0
risk_rows=0
```

候选 ROM：

```text
rom/narutorpg3_chs_patcher_v36_no_pre03_spaces.nds
SHA256 B29FEA1B5B7BBD5E2010BD5AF1262676B6B71CB1D6E126847BECCB9A71954BB9
```

