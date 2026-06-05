# v23 菜单/对白/说明静态修复记录

时间：2026-06-05

候选 ROM：

```text
rom/narutorpg3_chs_patcher_v23_menu_dialog_desc_fusion12_r2.nds
```

默认资源校验 ROM：

```text
rom/narutorpg3_chs_patcher_v23_default_resource_check.nds
```

本轮未启动或操作 DeSmuME/MCP；运行时验证继续交给用户手动测试。

## 修复范围

1. 对 `zh_txt_2ef7aa25_000758_0027`、`zh_txt_6b929156_0001A6_0005`、`zh_txt_6b929156_0001FA_0006` 启用原控制位分段写回，保持原始 `CTRL_0103/CTRL_0002/CTRL_0000/CTRL_0001` 或 `CTRL_0001` 的绝对位置。
2. 将已知说明表的 NUL4 记录改为译文后立即写入 `00 00 00 00`，后续零填充，避免短说明后面的全角空格被渲染成空白页或占位符。
3. 扩展 `CTRL_0000` 固定子槽位写回到成员、保存、商店、技能、阵型、通灵、Wi-Fi 好友等菜单说明记录；`msg/wifi/friend_msg.msg` 不再整体默认排除，只保留 `msg/wifi/kinshi_msg.msg` 排除。
4. 补 `menu_overlay_0003_044584` 的固定宽度状态字段覆盖，保留左侧状态页前导全角空格和每个标签的原字段宽度。
5. 补 `overlay_0003:0x44618` 的运行时“メンバーせってい”副本，局部替换为“成员设置”，不覆盖后续结构字段。

## 静态验证

- 构建目录：`patcher/work/build_20260605_103608`
- 审计：`checked=5862`、`excluded=1`、`after_control_mismatch=0`、`overflow=0`、`missing=0`
- 写回：`text_rows=5859`、`menu_rows=289`
- 文本逐条重算并对比 workdir：`mismatches=0`
- 菜单逐条重算并对比 workdir：`mismatches=0`
- 目标对白 3 条均命中 `preserve_fixed_control_slot_offsets`
- `CTRL_0000` 子槽位写回命中 36 条；NUL4 提前终止命中 571 条
- `ndstool -i`：Header CRC OK / Banner CRC OK
- 默认资源构建 ROM 与 rebuild-text-assets ROM 的 SHA256 相同：

```text
9B18A0B4B6DA1BC8B8BC2C337B12421285F46B7C2E6B285C598B1F066118A3CC
```

## 残留扫描

对用户截图相关 CP932 关键字做静态扫描：

- `じぶんのなまえ`
- `しょぞくする里`
- `ひとことコメント`
- `メンバー`
- `メンバーせってい`
- `スタミナ`
- `チャクラ`
- `こうげき`
- `ぼうぎょ`
- `すばやさ`
- `にんりょく`
- `フィールドコマンド`
- `ステータス`

上述关键字在 v23 r2 workdir 中均为 0 命中。

仍有 `忍術` 命中 `data/download/n3dl.srl:0xCE011`。该文件是下载包嵌入副本，不是当前截图菜单的普通文本/overlay 来源，本轮不作为运行时菜单残留处理。

## 待手动验证

- 两条新报告对白是否不再提前跳过后半句。
- 道具/忍术说明是否不再显示空白页或 `@@` 占位符。
- 装备页、状态页左侧字段是否对齐。
- 用户/成员菜单说明是否已翻译并且首屏显示。
