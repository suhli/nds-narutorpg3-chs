# 文本回写冒烟计划

## 背景

`plan/code-table-extraction.md` 已完成译文冻结、字符集提取、中文码表分配和字体 manifest 生成。当前可用输入为：

```text
text/code_table/frozen_translation.tsv
text/code_table/zh_code_table.tsv
text/code_table/font_manifest.json
plan/cache/code-table-extraction/handoff-to-text-writeback.md
```

本计划承接码表阶段，进入最小文本回写闭环。第一步只生成编码预览和容量风险报告，不修改 ROM，不打包 ROM。

## 必要上下文

- 原版 ROM `rom/origin.nds` 只能作为输入读取，不能覆盖、原地 patch 或作为打包输出。
- `frozen_translation.tsv` 是当前回写输入，包含来源文件、偏移、原始字节、日文、译文、控制 token 和原槽位长度。
- `zh_code_table.tsv` 当前冻结编码范围为 `0xF040..0xFAAB`，共 1986 项，按 SJIS 形状分配；`0xFA40` 因 raw word 冲突被跳过。
- 前一阶段的长度校验不是最终回写模型；它主要用于翻译 chunk 对齐，不能直接等同于 ROM 写回字节长度。
- 行尾 ASCII padding 是翻译对齐产物，不得静默当作普通可见文本编码，也不得在 Stage 1 作为已确定写回策略。
- 普通 ASCII 是否沿用原编码、加入扩展码表或按来源路径特殊处理，仍需单独决策。
- `{CTRL_xxxx}` 必须恢复为控制字节候选，并用原始 `raw_hex` 或 dump 边界验证后才允许进入写回样本。
- 中文码点写回端序不得默认。编码预览必须保留 `raw_hex`、原文 token、候选编码 bytes 和端序判断依据；无法判断的行必须标记风险，不能进入 Stage 2 样本。

## 目标

- 建立 `zh_text + 控制 token -> 候选写回 bytes` 的可复现编码预览。
- 生成固定槽容量风险报告，区分可尝试样本和必须后续处理的文本。
- 隔离 ASCII、padding、控制符验证和中文码点端序风险。
- 选出少量低风险 Stage 2 写回候选，但 Stage 1 不实际写回。
- 后续在独立 ROM 中验证最小文本替换闭环。

## 非目标

- 不全量回写文本。
- Stage 1 不修改 NitroFS 文件，不打包 ROM，不运行模拟器。
- 不覆盖 `rom/origin.nds` 或任何已知基准 ROM。
- 不在控制符、端序或 ASCII 策略未确认时做批量替换。

## 产物

### 工具

```text
tools/encode_translation_text.py
```

### 数据与报告

```text
text/writeback/encoded_preview.tsv
text/reports/writeback-capacity-report.json
```

### 计划缓存

```text
plan/cache/text-writeback-smoke/stage0-plan-setup.md
plan/cache/text-writeback-smoke/stage1-encoder-and-capacity.md
plan/cache/text-writeback-smoke/stage2-sample-writeback.md
plan/cache/text-writeback-smoke/stage3-rom-packaging.md
plan/cache/text-writeback-smoke/stage4-desmume-validation.md
plan/cache/text-writeback-smoke/handoff-to-full-writeback.md
```

## 硬性进入条件

Stage 2 样本必须同时满足：

- 固定槽容量不超限。
- 控制符已由原始 `raw_hex` 或既有 dump 边界验证。
- 无普通 ASCII 策略风险。
- 无 padding 歧义。
- 无中文码点端序不确定风险。
- 来源文件、偏移、记录号可定位。
- 不涉及 `rom/origin.nds` 输出或覆盖。

不满足任一条件的行只能作为报告项，不能进入样本写回。

## 阶段

### Stage 0: 计划接续与输入确认

状态：已完成。

目标：

- 读取 `plan/state.yaml` 和码表阶段 handoff。
- 使用计划生成与评审 subagent 生成并评审本计划。
- 把当前统一入口切换到本计划。

缓存：

```text
plan/cache/text-writeback-smoke/stage0-plan-setup.md
```

### Stage 1: 编码预览与容量风险扫描

状态：已完成。

目标：

- 实现 `tools/encode_translation_text.py`。
- 从 `frozen_translation.tsv` 和 `zh_code_table.tsv` 生成候选写回 bytes。
- 对控制符恢复、中文码点端序、普通 ASCII、尾部 padding、码表缺失和固定槽容量分别打标签。
- 输出编码预览和容量报告。
- 记录可进入 Stage 2 的候选条件与剩余风险。

缓存：

```text
plan/cache/text-writeback-smoke/stage1-encoder-and-capacity.md
```

### Stage 2: 低风险固定槽样本回写

状态：已完成。

目标：

- 先完成中文扩展码端序验证；未验证前不选择写回样本。
- 只选择 Stage 1 判定可进入样本的少量文本。
- 在解包资源的副本中做固定槽替换。
- 不覆盖 `rom/origin.nds`。
- 记录样本来源文件、偏移、原始 bytes、候选写回 bytes 和恢复方式。

缓存：

```text
plan/cache/text-writeback-smoke/stage2-sample-writeback.md
```

### Stage 3: 字体资源集成与独立 ROM 打包

状态：已完成。

目标：

- 集成 font-dir 和样本文本资源。
- 使用独立输出 ROM，例如：

```text
rom/text_writeback_smoke.nds
```

- 不覆盖 `rom/origin.nds` 或任何已知基准 ROM。
- 记录解包目录、回包命令摘要、输出 ROM 和校验结果。

缓存：

```text
plan/cache/text-writeback-smoke/stage3-rom-packaging.md
```

### Stage 4: DeSmuME MCP 显示冒烟

状态：待开始。

目标：

- 加载 Stage 3 的独立 ROM。
- 记录验证入口、截图或内存观察摘要、失败现象和复现路径。
- 如果得到新的逆向发现，同步写入 `hack/`。

缓存：

```text
plan/cache/text-writeback-smoke/stage4-desmume-validation.md
```

### Stage 5: 交接到完整回写或扩容方案

状态：待开始。

目标：

- 汇总固定槽样本验证结果。
- 给出全量回写、文本池迁移、指针扩容或脚本重排的后续建议。
- 回写最终 handoff。

缓存：

```text
plan/cache/text-writeback-smoke/handoff-to-full-writeback.md
```

## 当前决策

- Stage 1 只做预览和报告，不写 ROM。
- 中文码点端序、控制符恢复和 ASCII 策略是 Stage 2 的硬门槛。
- Stage 3 输出必须是独立 ROM，默认候选为 `rom/text_writeback_smoke.nds`。

## 待验证风险

- 中文扩展码 `0xF040..0xFAAB` 在实际文本读取链路中的字节端序。
- `{CTRL_xxxx}` 与原始字节之间的边界对齐。
- 普通 ASCII 在不同文本类别中的显示路径。
- 尾部 padding 是否仅为翻译阶段产物，回写时是否需要保留或重算。
- 固定槽超长文本的扩容策略。

## 2026-06-04 v19 合并修复候选

已构建 `rom/narutorpg3_chs_patcher_v19_allfix_rebuild_fusion12.nds`，该候选通过 `--rebuild-text-assets` 从冻结译文完整重建。

本轮合并：

- 全量写回切换为 1x1/1x2 双模式字体缓存；
- 状态与升级组合字段按原字符宽度翻译，避免固定 UI 坐标错位；
- 保留 10 条场景专用 message 尾控制序列，避免句末符号和自动跳过；
- 保留普通 message 原始 `03 00` 位置和 `81 40` 安全填充策略。

静态验证：

- 写回文本 5835 条逐条匹配，差异 0；
- 菜单 287 条全部 `ready`，关键 1x1 菜单槽位逐字节匹配；
- `after_control_mismatch_rows=0`、`overflow_rows=0`、`missing_char_rows=0`；
- Header CRC OK / Banner CRC OK；
- 文本与菜单缺字为 0，仅 TTF 保留占位字符 `U+E0FD` 缺失。

当前阶段仍为运行时回归验证，未标记完成。

## 2026-06-04 v20 同步双模式候选

v19 运行测试确认延迟换页会导致标题菜单 1x2 文本只显示占位方框，因此 v19 已判定无效。

新候选：

```text
rom/narutorpg3_chs_patcher_v20_dual_immediate_fusion12.nds
```

v20 使用同步双模式字体缓存：

- `R2=0x20` 进入独立 1x1 同步换页助手；
- `R2=0x40` 保留 v15 已运行显示正常的 1x2 同步双槽实现；
- 不再劫持绘制入口做延迟换页。

静态验证：

- v20 实际 1x2 hook 与 v15 逐字节相同；
- 分流入口、1x1 助手、1x2 hook 均与生成结果一致且互不重叠；
- overlay 绘制入口保持原版；
- 文本 5835 条实际写回差异 0；
- 菜单 287 条全部 `ready`；
- Header CRC OK / Banner CRC OK。

当前阶段仍为运行时回归验证，重点确认 1x1 和 1x2 页面能够连续切换并同时正常显示。

## 2026-06-04 v20 结构回归排查

v20 运行测试确认 1x1/1x2 同步双模式已经可用。剩余问题集中在文本来源漏扫和结构不安全写回：

- 商店菜单的运行时来源包含场景消息，不只来自已翻译的 overlay 菜单副本；
- 状态页漏译的 `そうびをみる` 未进入当前菜单翻译表；
- `msg/menu/top_menu_msg.msg`、`msg/menu/status_menu_msg.msg`、`msg/jyutu_msg.msg` 包含多个固定子槽位合并成单条抽取记录的格式；
- 当前写回器没有保持这些子槽位和分隔符的原始绝对偏移，导致暂停菜单说明、技能描述和状态说明错位；
- `msg/menu/jinkei_menu_msg.msg` 含文本与二进制混合记录，整体按纯文本重编码可能导致进入“阵型”后卡死；
- 保存“否”不可见和读取存档名称多字同样需要按固定槽位宽度及尾部参数原位修复。

当前决策：下一候选 ROM 构建前，先实现按原始子槽位边界写回的结构安全路径，并确保混合记录中未确认可替换的字节与原版逐字节一致。

详细记录：`plan/cache/text-writeback-smoke/v5-regression-20260603/v20-structure-triage.md`。

## 2026-06-04 v21 结构安全写回候选

已构建：

```text
rom/narutorpg3_chs_patcher_v21_structslot_overlayfix_fusion12.nds
```

本轮修复：

- 合并消息记录按原始 `CTRL_0000` 子槽位绝对偏移原位写回，不再把整条译文压到记录开头。
- 阵型混合记录只替换已确认文本范围，其余二进制字段保持原版。
- 恢复 7 条内嵌“是/否”记录的定宽原位翻译。
- 翻译 6 条商店场景消息中的引号前菜单选项。
- 补充状态页 `そうびをみる` 对应的 overlay 固定槽位。

静态验证：

- 文本 5842 条、菜单 288 条逐条实际字节与预期差异均为 0。
- 7 条合并子槽位记录的所有分隔符偏移保持原版。
- 阵型混合记录和纯“是/否”记录的未确认二进制尾部保持原版。
- 文本和菜单缺字为 0，仅字体保留占位字符 `U+E0FD` 告警。
- `ndstool -i` Header CRC OK / Banner CRC OK。

按项目约定，运行时验证等待用户手动完成；除非用户明确提出，不使用 DeSmuME MCP 调试。详细记录见 `plan/cache/text-writeback-smoke/v5-regression-20260603/v21-static-validation.md`。

## 2026-06-04 v22 控制结构与说明结束符候选

用户手动测试确认 v21 已清除此前回归 todo。v22 针对一条对白后半句跳过和说明页
首次进入为空的问题完成修复，并扫描同类结构。

最终候选：

```text
rom/narutorpg3_chs_patcher_v22_final_controlslot_nul4_fusion12.nds
```

本轮修复：

- 恢复目标对白及 10 条同类记录中被审计器误删的正文控制符，不改可见译文。
- 把 600 条说明消息末尾的 `00 00 00 00` 识别为真实 `NUL4` 结束符并原位保留。
- 将原始子槽位写回扩展到 7 类说明表，覆盖 16 条合并固定子槽位记录。
- 菜单资源重建继续保留“查看装备”和四条中文存档文件名间隔点。

静态验证：

- 文本 5842 条、菜单 288 条实际写回差异为 0。
- 600 条 `NUL4` 结束符和 16 条合并记录子槽位分隔符位置差异均为 0。
- 重建资源与默认冻结资源构建结果逐文件一致，最终 ROM SHA256 相同。
- 文本和菜单缺字为 0，仅字体保留占位字符 `U+E0FD` 告警。
- `ndstool -i` Header CRC OK / Banner CRC OK。

当前阶段继续等待用户手动验证目标对白、说明首屏和其他同类说明；本轮未使用
DeSmuME/MCP。详细记录见
`plan/cache/text-writeback-smoke/v5-regression-20260603/v22-control-slot-triage.md`。

## 2026-06-05 v23 菜单/对白/说明修复候选

用户手动测试 v22 后报告 6 类新问题：两条对白后半句不显示或跳过、部分菜单仍未翻译、装备/状态页左侧字段错位、道具/忍术说明占位符、菜单说明首屏空白。本轮按静态规则修复，未使用 DeSmuME/MCP。

最终候选：

```text
rom/narutorpg3_chs_patcher_v23_menu_dialog_desc_fusion12_r2.nds
```

本轮修复：

- 对 `zh_txt_2ef7aa25_000758_0027`、`zh_txt_6b929156_0001A6_0005`、`zh_txt_6b929156_0001FA_0006` 按原控制位分段写回，避免 `CTRL_0001` 或地点高亮控制提前移动。
- 已知说明表的 NUL4 记录改为译文后立即终止，避免全角空格 padding 形成空白页或占位符。
- `CTRL_0000` 固定子槽位写回扩展到 36 条菜单/说明记录，并放开 `msg/wifi/friend_msg.msg` 的 18 条好友/用户菜单文本写回。
- 补 `overlay_0003:0x44584` 状态页固定宽度行和 `overlay_0003:0x44618` “成员设置”运行时副本。

静态验证：

- 审计 `checked=5862`、`excluded=1`、`after_control_mismatch=0`、`overflow=0`、`missing=0`。
- 实际写回 `text_rows=5859`、`menu_rows=289`；文本逐条字节比对差异 0，菜单逐条字节比对差异 0。
- 截图相关 CP932 日文关键字扫描为 0，除 `data/download/n3dl.srl` 内嵌下载包副本的 `忍術` 外。
- `ndstool -i` Header CRC OK / Banner CRC OK。
- 默认资源构建 `rom/narutorpg3_chs_patcher_v23_default_resource_check.nds` 与 rebuild-text-assets 候选 SHA256 相同：`9B18A0B4B6DA1BC8B8BC2C337B12421285F46B7C2E6B285C598B1F066118A3CC`。

详细记录见 `plan/cache/text-writeback-smoke/v5-regression-20260603/v23-menu-dialog-description-triage.md`。运行时验证继续由用户手动完成。

## 2026-06-05 v24 存档选项、占位符和装备对齐候选

用户手动测试 v23 后反馈：存档覆盖确认中“否”仍不出现，部分菜单说明存在占位符或首屏空白，装备属性与“护腿”分类错位。本轮按静态规则修复，未使用 DeSmuME/MCP。

候选 ROM：

```text
rom/narutorpg3_chs_patcher_v24_save_equip_trim_fusion12.nds
SHA256 71B648ADA7B5F0D869B10A30B6C448DDB3EBDD48EBCB3F33D7E0A9B9CC173451
```

资源重建校验 ROM：

```text
rom/narutorpg3_chs_patcher_v24_rebuild_resource_check.nds
SHA256 71B648ADA7B5F0D869B10A30B6C448DDB3EBDD48EBCB3F33D7E0A9B9CC173451
```

修复内容：

- overlay_0002 保存确认选项按原始可见宽度补齐，避免“是”后提前 `00 00` 终止导致“否”不可见。
- 固定 `CTRL_0000` 子槽位保留原始绝对偏移，译文后剩余空间改为 `00` 填充。
- `msg/menu/*` 与 `msg/wifi/friend_msg.msg` 的普通 `03 00` 菜单说明改为译文后立即结束，尾部 `00` 填充，用于清理空白说明页。
- 装备属性效果表改用短译，装备分类 overlay 行按原始宽度写入“武器 / 防具　/ 护腿　　”。
- 护腿类物品名和说明加入短译覆盖，降低装备页和底部说明溢出风险。

静态验证：

- 结构审计 `checked=5862`、`excluded=1`、`after_control_mismatch=0`、`overflow=0`、`missing=0`。
- 菜单 overlay `selected_rows=289`、`ready=289`、`missing_font_chars=""`。
- 实际 ROM 写回逐字节核对：`text_mismatches=0`、`menu_mismatches=0`。
- `ndstool -i`：Header CRC OK / Banner CRC OK。
- 文本和菜单缺字为 0，仅字体保留占位字符 `U+E0FD` 告警。

详细记录见 `plan/cache/text-writeback-smoke/v5-regression-20260603/v24-save-equip-trim.md`。运行时验证继续由用户手动完成。

## 2026-06-05 v25 同类结构全量审计候选

按用户要求，对 v24 之前发现的同类结构问题做全量静态扫描。本轮未使用 DeSmuME/MCP。

候选 ROM：

```text
rom/narutorpg3_chs_patcher_v25_full_struct_audit_fusion12.nds
SHA256 93043824CD5247B98CEF499B0232682191D30076AE82E457DB061F82FE2ADDAD
```

资源重建校验 ROM：

```text
rom/narutorpg3_chs_patcher_v25_rebuild_resource_check.nds
SHA256 93043824CD5247B98CEF499B0232682191D30076AE82E457DB061F82FE2ADDAD
```

本轮新增：

- 新增结构风险审计脚本 `tools/audit_v24_structural_risks.py`，并同步到 `patcher/tools/`。
- Wi-Fi 六类消息源加入固定 `CTRL_0000` 子槽位原位写回，新增覆盖 39 条，固定子槽位总覆盖 75 条。
- `msg/wifi/connect_msg.msg`、`msg/wifi/error_msg.msg` 加入普通 `03 00` 提前结束规则，覆盖 6 条 UI 提示。
- `msg/menu/battle_result_msg.msg` 加入 NUL4 提前结束规则，覆盖 1 条战斗结果菜单提示。

最终审计：

- 文本侧同类结构风险为 0。
- 剩余 7 条 overlay 间距观察项暂不自动修；它们无结构分隔符破坏，且当前译文已保留必要可见空格或属于单标签尾部 padding。
- 实际 ROM 写回逐字节核对：`text_mismatches=0`、`menu_mismatches=0`。
- `ndstool -i`：Header CRC OK / Banner CRC OK。
- 文本和菜单缺字为 0，仅字体保留占位字符 `U+E0FD` 告警。

详细记录见 `plan/cache/text-writeback-smoke/v5-regression-20260603/v25-full-structural-audit.md`。运行时验证继续由用户手动完成。

## 2026-06-05 v26 控制符、占位符与固定布局候选

用户手动测试 v25 后反馈：`zh_txt_dc122c8a_000BD4_0040` 与 `zh_txt_dc122c8a_000C2C_0041` 之间多出空行，后一条在“「按下”后乱码并导致后续对白颜色异常；道具和对战设置说明在半句后乱码；一个“攻击 / 防御 / 速度”布局仍错位。本轮按静态规则修复，未使用 DeSmuME/MCP。

候选 ROM：
```text
rom/narutorpg3_chs_patcher_v26_control_placeholder_layout.nds
SHA256 367E608BC643640F72E108E83554974F9F12CC87D6BF3FC9B62B3FF71D25F1CD
```

修复内容：
- 控制符外可见 ASCII 统一转全角；已确认结构尾部的 `N`/`4` 单字节参数单独保留。
- `zh_txt_dc122c8a_000BD4_0040` 改为固定控制位原位写回；`zh_txt_dc122c8a_000C2C_0041`、道具说明、好友/对战设置说明中的半角 `Y`、`1`、`/` 等不再以单字节写入。
- 修复错误半角标点行 `zh_txt_de7d406d_000124_0004`，并清理两条 ASCII 省略号风险。
- 将 `攻击 / 防御 / 速度` 等 8 条 overlay 固定间距文本改为固定宽度覆盖。

静态验证：
- 文本替换检查 5858 条，控制符外可见 ASCII 风险 0，保留结构尾部 ASCII 参数 2 条。
- overlay 结构和固定间距风险 0。
- 实际工作目录逐字节核对：文本 5858 条、菜单 289 条，mismatch=0。
- 默认冻结资源构建与 `--rebuild-text-assets` 构建 SHA256 一致。
- `ndstool -i`：Header CRC OK / Banner CRC OK。
- 文本和菜单缺字为 0，仅字体保留占位字符 `U+E0FD` 告警。

详细记录见 `plan/cache/text-writeback-smoke/v5-regression-20260603/v26-control-placeholder-layout.md`。运行时验证继续由用户手动完成。
