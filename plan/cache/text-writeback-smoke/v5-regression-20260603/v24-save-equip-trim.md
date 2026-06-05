# v24 存档选项、占位符和装备对齐修复

## 背景

用户手动测试 v23 后反馈：

- 存档覆盖确认中“否”仍不出现。
- 菜单说明里仍有占位符或空行，部分说明需要按 A/B 后才显示。
- 装备属性与“护腿”分类在 overlay UI 中错位。

按用户要求，本轮未使用 DeSmuME/MCP，只做静态结构核对、资源重建、回包和 `ndstool` 头校验。

## 根因

### 存档“否”

保存确认选项来自 `overlay_0002.bin:0x12C0C` 一类固定宽度 overlay 记录。v23 写成：

```text
F0 8C 00 00 01 00 F5 C7 ...
```

`是` 后面的 `00 00` 在运行时会被当作选项列表终止，导致后面的 `否` 不显示。

修复规则：对 overlay_0002 的保存/确认选项行，先把可见文本段补到原始可见宽度，再用 `00` 补齐槽位尾部。v24 目标字节：

```text
F0 8C 81 40 01 00 F5 C7 81 40 81 40 00 00 00 00
```

### 说明占位符和空页

固定 `CTRL_0000` 子槽位记录此前会把译文后剩余容量填成全角空格。部分运行时说明框会把这些空格或残留容量当作可显示正文，表现为首屏空白、需要再按 A/B，或显示 `@` 占位符。

修复规则：

- `CTRL_0000` 合并记录继续保持每个子槽位的原始绝对偏移。
- 每个译文子槽位写完后，子槽位内部剩余空间改为 `00` 填充。
- `msg/menu/*` 与 `msg/wifi/friend_msg.msg` 中普通 `03 00` 结束的菜单说明，`03 00` 改为紧跟译文，尾部 `00` 填充，避免空白说明页。
- 剧情 message 不套用该规则，仍保留原始结束符位置。

### 装备/护腿错位

装备页上方属性效果文本来自 `msg/taityou_kouka.msg`，不是 overlay。原译文如“攻击力提升/防御力下降”超过固定显示区域，导致右侧数值和后续字段错位。

修复规则：该效果表改用短标签：

```text
攻升 / 防降 / 防升 / 攻降 / 速升 / 速降
```

装备分类行 `menu_overlay_0003_04430C` 必须保持原始行宽，v24 写回为：

```text
武器
防具　
护腿　　
```

长护腿类物品名和说明也加入人工短译，避免底部说明框溢出。

## 代码与资源变更

- `patcher/tools/build_text_writeback_smoke_rom.py`
- `tools/build_text_writeback_smoke_rom.py`
  - 新增菜单/好友说明的提前 `03 00` 结束规则。
  - 固定子槽位改为译文后 `00` 填充。
- `patcher/tools/build_full_writeback_menu_overlay_rom.py`
- `tools/build_full_writeback_menu_overlay_rom.py`
  - overlay_0002 固定选项行按原始可见宽度补全角空格，再补 `00`。
- `patcher/tools/prepare_overlay_menu_translations.py`
- `tools/prepare_overlay_menu_translations.py`
  - 装备分类 overlay 行改为固定宽度人工替换。
- `patcher/resources/text/translation-struct-manual-overrides.tsv`
- `plan/cache/text-writeback-smoke/translation-struct-manual-overrides.tsv`
  - 增加属性效果、护腿类物品名和说明的短译覆盖。

## 静态验证

结构审计：

```text
checked=5862
excluded=1
issue_rows=298
auto_adjusted=1027
after_control_mismatch=0
overflow=0
missing=0
```

菜单 overlay 预处理：

```text
selected_rows=289
status_counts.ready=289
missing_font_chars=""
```

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

两份 ROM 哈希一致，说明冻结资源构建和 `--rebuild-text-assets` 资源重建构建一致。

`ndstool -i` 校验：

```text
Header CRC OK
Banner CRC OK
```

逐字节核对：

```text
text_mismatches=0
menu_mismatches=0
```

抽查字节：

- `overlay/overlay_0002.bin:0x12C0C`：`是` 与 `否` 之间不再出现提前终止的 `00 00`。
- `msg/wifi/friend_msg.msg:0x8`：译文后提前结束，原子槽位分隔偏移仍保持。
- `msg/taityou_kouka.msg:0x8`：属性效果短译写入，子槽位尾部为 `00`。
- `param/item_data.dat:0x66B4`：护腿类物品短名写入，尾部为 `00`。

缺字报告仍只有字体占位字符 `U+E0FD`，文本和菜单缺字均为 0。

## 待手动验证

请优先验证：

- 存档覆盖确认中“是/否”是否同时显示。
- 好友/用户/菜单底部说明是否不再出现首屏空白和 `@` 占位符。
- 装备页属性效果是否不再错位。
- 装备分类和护腿类物品名/说明是否不再挤占后续字段。
