# v26 控制符、占位符与固定布局修复

## 背景

用户手动测试 v25 后反馈三类新问题：

- `zh_txt_dc122c8a_000BD4_0040` 与 `zh_txt_dc122c8a_000C2C_0041` 之间多出空行，后一条只显示到“「按下”后乱码并自动结束，之后对白颜色保持蓝色。
- 道具说明、对战设置说明在“少量恢复”“确认”后出现乱码。
- 一个只显示“攻击 / 防御 / 速度”的菜单布局仍然错位。

本轮未使用 DeSmuME/MCP；运行时验证继续由用户手动完成。

## 根因

这些问题的共同根因是“可见文本中残留单字节 ASCII”或“overlay 固定布局被短译文压缩”。

- `zh_txt_dc122c8a_000C2C_0041` 的 `Y按钮` 写成单字节 `59`，它位于 `CTRL_0103/CTRL_0002` 高亮段内。渲染器把该单字节当成非预期控制/参数流后，高亮闭合段未正常消费，导致后续对白颜色异常。
- `msg/item_msg.msg` 中 `少量恢复1人的体力` 的 `1` 写成单字节 `31`，所以画面只渲染到“少量恢复”。
- `msg/wifi/friend_msg.msg` 中 `确认/修改一句话评论` 的 `/` 写成单字节 `2F`，所以只渲染到“确认”。
- `zh_txt_dc122c8a_000BD4_0040` 是控制位敏感对白，短译文 padding 不能全部堆到记录尾部，否则运行时会形成额外空行；应按原始控制位分段补齐。
- `overlay_0003:0x442A0` 的“こうげき　ぼうぎょ　すばやさ”是固定间距三标签，短译文 `攻击　防御　速度` 会改变标签起点。

## 修复

- 写回器新增 `normalized_message_text` 的可见 ASCII 归一化：控制符 `{CTRL_xxxx}` 内部不动，控制符外的 `0x20..0x7E` 可见字符统一转全角。
- 保留 2 条已确认结构尾部单字节参数，不作为可见文本翻译：
  - `zh_txt_bb92057e_000008_0000` 尾部 `{CTRL_0008}{CTRL_0000}N`
  - `zh_txt_b91ed4cf_000008_0000` 尾部 `{CTRL_0008}{CTRL_0000}4{CTRL_0000}{CTRL_5400}{CTRL_0000}{CTRL_7C00}`
- 新增/调整文本覆盖：
  - `zh_txt_dc122c8a_000BD4_0040` 加入固定控制位原位写回。
  - `zh_txt_de7d406d_000124_0004` 从错误半角引号感叹号恢复为 `「！」`。
  - `zh_txt_6405d86e_000088_0003`、`zh_txt_301f6085_0000BC_0002` 的 ASCII 省略号改为中文/全角省略号。
  - `zh_txt_805b124c_000526_0007` 缩短 Wi-Fi/DS 相关可见文本，避免全角化后超槽。
- 固定宽度 overlay 覆盖扩展到 8 条：
  - `menu_overlay_0003_0442A0`：攻击 / 防御 / 速度。
  - `menu_overlay_0000_030100`：提升 / 相同 / 下降 / 装备中。
  - `menu_overlay_0000_0301F8`：当前经验值。
  - `menu_overlay_0000_030214`：距下一级还差。
  - `menu_overlay_0002_0128B8`：获得了！
  - `menu_overlay_0003_045228`：通灵纸暗号提示。
  - `menu_overlay_0003_0452B8`、`menu_overlay_0003_0452D8`：存档文件名。

## 控制符和占位符规则

- `CTRL_0001`：正文中的换行/换页类控制。对控制位敏感对白，必须按原始控制位分段写回，不能把译文整体压到记录开头。
- `CTRL_0000`：在合并说明表中是固定子槽位边界，也可能是高亮段结束参数的一部分。合并记录必须按原始子槽位偏移原位写回。
- `CTRL_0103` + `CTRL_0002`：常见的颜色/高亮开始序列；对应的 `CTRL_0103` + `CTRL_0000` 用于结束/复位。该范围内的可见文字仍必须是双字节字符，不能残留半角 ASCII。
- `CTRL_0008`：在少数大表尾部后接结构参数，本轮确认的 `N` 与 `4` 是结构尾部，不是可见文本。
- `03 00`：普通 message 结束符。剧情对白默认保留原位置；菜单/好友说明类短文本可提前放到译文后，并用 `00` 填尾。
- `00 00 00 00`：部分说明表的真实 NUL4 结束符。已知说明表应在译文后立即写入 NUL4，再用 `00` 填尾，避免空白首屏。
- overlay 固定布局：同一条 overlay 字符串含多个标签或依赖原始间距时，译文必须用全角空格补到原始可见宽度，不能短译后直接 `00` 填尾。

## 全量审计

审计输出：

```text
plan/cache/text-writeback-smoke/v5-regression-20260603/v26-control-placeholder-layout-audit.json
plan/cache/text-writeback-smoke/v5-regression-20260603/v26-control-placeholder-layout-audit.tsv
plan/cache/text-writeback-smoke/v5-regression-20260603/v26-writeback-byte-compare.json
```

结果：

- 文本替换检查：5858 条，无编码错误。
- 控制符外可见 ASCII 风险：0。
- 已保留结构尾部 ASCII 参数：2 条。
- overlay 结构/固定间距风险：0。
- 实际工作目录逐字节核对：文本 5858 条、菜单 289 条，mismatch=0。

## 候选 ROM

正式候选：

```text
rom/narutorpg3_chs_patcher_v26_control_placeholder_layout.nds
SHA256 367E608BC643640F72E108E83554974F9F12CC87D6BF3FC9B62B3FF71D25F1CD
```

资源重建检查：

```text
rom/narutorpg3_chs_patcher_v26_rebuild_resource_check2.nds
SHA256 367E608BC643640F72E108E83554974F9F12CC87D6BF3FC9B62B3FF71D25F1CD
```

说明：固定宽度 overlay 覆盖已进入资源重建规则，默认冻结资源构建与 `--rebuild-text-assets` 构建哈希一致。

静态验证：

- `ndstool -i`：两份 ROM 均 Header CRC OK / Banner CRC OK。
- 文本缺字 0，菜单缺字 0；仅字体保留占位 `U+E0FD` 仍报告缺字。
