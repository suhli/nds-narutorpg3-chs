# v25 同类结构全量审计

## 背景

用户要求全量检查此前发现的问题是否还有其他地方需要同类修复。本轮继续遵守“不使用 DeSmuME/MCP，运行时由用户手测”的规则，只做静态结构审计、补规则、回包和字节核对。

重点复查三类 v24 问题：

- 固定 `CTRL_0000` 子槽位被整条压缩写回。
- UI/菜单说明尾部全角空格 padding 导致空白页或占位符。
- overlay 固定宽度文本翻译后错位。

## 新增审计工具

新增：

```text
tools/audit_v24_structural_risks.py
patcher/tools/audit_v24_structural_risks.py
```

审计输出：

```text
plan/cache/text-writeback-smoke/v5-regression-20260603/v25-structural-risk-audit.json
plan/cache/text-writeback-smoke/v5-regression-20260603/v25-structural-risk-audit.tsv
```

## 发现与处理

### Wi-Fi 合并消息记录

首次审计发现 `msg/wifi/*.msg` 中还有 39 条合并 `CTRL_0000` 的记录，来源包括：

```text
msg/wifi/btlres_msg.msg
msg/wifi/connect_msg.msg
msg/wifi/error_msg.msg
msg/wifi/rule_msg.msg
msg/wifi/taisen_msg.msg
msg/wifi/vs_msg.msg
```

这些记录和之前菜单说明同类：一条抽取记录里包含多个固定子字符串。试跑原子槽位写回全部通过：

```text
ok=39
fail=0
```

已将这些来源加入 `FIXED_SUBSLOT_SOURCE_FILES`，因此 v25 固定子槽位覆盖从 36 条扩大到 75 条。

### Wi-Fi 设置/错误提示

审计还发现 6 条普通 `03 00` 结束的 Wi-Fi 设置/错误说明仍保留译文后的全角 padding。它们不是剧情脚本，属于 UI 提示文本：

```text
msg/wifi/connect_msg.msg: 4 rows
msg/wifi/error_msg.msg: 2 rows
```

已将这两个来源加入 `EARLY_MESSAGE_TERMINATOR_SOURCE_FILES`，译文后立即写 `03 00`，尾部 `00` 填充。

### battle result NUL4 提示

`msg/menu/battle_result_msg.msg` 中 1 条 NUL4 菜单提示仍保留全角 padding：

```text
zh_txt_dce51332_000008_0000: 获得了经验值！
```

已加入 `EARLY_NUL4_TERMINATOR_SOURCE_FILES`。

### overlay 间距候选

最终审计仍列出 7 条 overlay 间距观察项：

```text
menu_overlay_0000_030100
menu_overlay_0000_0301F8
menu_overlay_0000_030214
menu_overlay_0002_0128B8
menu_overlay_0003_045228
menu_overlay_0003_0452B8
menu_overlay_0003_0452D8
```

逐条检查后暂不自动修：

- 这些记录没有 `00 00`/`01 00` 结构分隔符被破坏。
- 当前译文已包含必要的可见全角空格，或是单个提示/文件名标签，尾部 `00` 不会截断后续子项。
- 其中 `menu_overlay_0002_0128B8` 已是人工 override，用于保留“获得了！”前的道具名占位宽度。

若用户手测这些具体页面仍出现对齐问题，再按截图补固定宽度 row override。

## 最终审计结果

```text
risk_rows=7
risk_counts.overlay_fixed_width_spacing_candidate=7
text structural risk rows=0
```

已覆盖统计：

```text
fixed_subslot_row_count=75
early_03_row_count=107
early_nul4_row_count=572
menu visible-span padding rows=9
menu fixed-width override rows=4
```

## 候选 ROM

```text
rom/narutorpg3_chs_patcher_v25_full_struct_audit_fusion12.nds
SHA256 93043824CD5247B98CEF499B0232682191D30076AE82E457DB061F82FE2ADDAD
```

资源重建校验：

```text
rom/narutorpg3_chs_patcher_v25_rebuild_resource_check.nds
SHA256 93043824CD5247B98CEF499B0232682191D30076AE82E457DB061F82FE2ADDAD
```

两份 ROM 哈希一致。

## 静态验证

`ndstool -i`：

```text
Header CRC OK
Banner CRC OK
```

逐条字节核对：

```text
text_rows=5859
menu_rows=289
text_mismatches=0
menu_mismatches=0
```

缺字：

```text
missing_chars_text_count=0
missing_chars_menu_count=0
missing_chars_font_count=1
missing_chars_all=U+E0FD
```

## 待手动验证

除 v24 已列出的存档、菜单说明、装备页外，建议额外顺手验证：

- Wi-Fi 设置/错误提示页是否不再有空白说明页。
- Wi-Fi 对战、好友代码、规则、对手信息等列表是否没有错位或跳项。
- 战斗结果页“获得经验值”提示是否没有额外空白行。

