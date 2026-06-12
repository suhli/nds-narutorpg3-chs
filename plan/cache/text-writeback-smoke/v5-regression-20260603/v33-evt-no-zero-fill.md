# v33 事件脚本 message 排除零填充早停候选

## 背景

用户手测 v32 后反馈：`msg/fld/evt/000.m` 中 `"火影大人，糟了！"` 后，本应连续显示的 `0x1DE..0x358` 多条对白全部跳过，直接进入 `txt_2ef7aa25_000392_0014`。

受影响片段属于 `msg/fld/evt/*.m` 事件脚本消息。该类记录在 dump 中大量带有 `dump artifact: evt message header`，说明文本前缀中混有事件对白头。v32 把普通 message 的 `03 00` 提前后，用 `00` 填充原槽位剩余空间；这些 `00` 在事件脚本消息中会影响后续事件流调度，不能作为中间 padding。

## 修复策略

`--early-message-terminator-zero-fill` 继续保留，但适用范围收窄：

- `msg/fld/evt/` 事件脚本消息不再参与普通 message 早停零填充。
- 这些事件脚本消息恢复为保留原始 `03 00` 结束符位置。
- 非事件脚本的普通 message 仍可使用 `译文 + 03 00 + 00 padding`。

新增代码规则：

```text
EVENT_SCRIPT_MESSAGE_SOURCE_PREFIXES = ("msg/fld/evt/",)
can_rewrite_ordinary_message_terminator(row, extra)
```

## 候选 ROM

```text
rom/narutorpg3_chs_patcher_v33_evt_no_zero_fill.nds
SHA256 33047C77BAF350B393D8156A63571A0DE7D13DFBBED833F7E752E49086B00A38
```

构建目录：

```text
patcher/work/build_20260612_120341
```

记录文件：

```text
plan/cache/text-writeback-smoke/v5-regression-20260603/v33-evt-no-zero-fill-records.json
plan/cache/text-writeback-smoke/v5-regression-20260603/v33-evt-no-zero-fill-structural-audit.json
plan/cache/text-writeback-smoke/v5-regression-20260603/v33-evt-no-zero-fill-structural-audit.tsv
```

## 静态验证

- `ndstool -i`：Header CRC OK / Banner CRC OK。
- Python AST 语法检查通过。
- 全量结构审计 `risk_rows=0`。
- `early_03_row_count=1816`，比 v32 的 3179 少，差异主要来自事件脚本消息被排除。
- `msg/fld/evt` 事件脚本消息共 1389 条，其中 `early_03_zero_fill_after_terminator=0`。
- 用户指出的 7 条目标记录全部恢复为 `message_terminator_position=preserved_original_end`。
- 直接二进制核对 `msg/fld/evt/000.m`：
  - `zh_txt_2ef7aa25_0001DE_0007`：`03 00` 位于 `source_byte_len - 2`。
  - `zh_txt_2ef7aa25_000222_0008`：`03 00` 位于 `source_byte_len - 2`。
  - `zh_txt_2ef7aa25_000274_0009`：`03 00` 位于 `source_byte_len - 2`。
  - `zh_txt_2ef7aa25_000292_0010`：`03 00` 位于 `source_byte_len - 2`。
  - `zh_txt_2ef7aa25_0002DA_0011`：`03 00` 位于 `source_byte_len - 2`。
  - `zh_txt_2ef7aa25_00031A_0012`：`03 00` 位于 `source_byte_len - 2`。
  - `zh_txt_2ef7aa25_000358_0013`：`03 00` 位于 `source_byte_len - 2`。
- 上述 7 条每条槽位内只有 1 个 `03 00`。
- 文本和菜单缺字为 0，字体仅保留既有占位符 `U+E0FD`。

## 运行时验证

本轮未使用 DeSmuME/MCP。需要用户手动验证 `msg/fld/evt/000.m` 这一段是否恢复连续对白。
