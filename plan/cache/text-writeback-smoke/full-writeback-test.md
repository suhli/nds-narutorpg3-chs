# 全量写回测试成品

更新时间：2026-06-02

## 状态

已完成构建，待模拟器完整测试。

## 用户要求

直接全部写回，做成成品 ROM 用于测试。

## 构建策略

本轮不再只写入少量低风险样本，而是把 `text/writeback/encoded_preview.tsv` 中 5863 条候选译文全部固定槽写回。

测试策略：

```text
中文/全角符号：使用 zh_code_table.tsv 的 big-endian 候选字节
ASCII：按单字节候选保留
尾部 padding：不写入译文，剩余空间用 00 填充
终止符：原记录有 raw_terminator_hex 时保留
rom/origin.nds：只读，不覆盖
```

## 构建命令

```text
.\.venv\Scripts\python.exe -B tools\build_text_writeback_smoke_rom.py --all --compact-records --work rom\unpacked\narutorpg3_chs_full_writeback_test --output rom\narutorpg3_chs_full_writeback_test.nds --records-out plan\cache\text-writeback-smoke\full-writeback-records.json
```

## 输出

```text
rom/narutorpg3_chs_full_writeback_test.nds
rom/unpacked/narutorpg3_chs_full_writeback_test/
plan/cache/text-writeback-smoke/full-writeback-records.json
```

## 写入摘要

```text
mode=all_fixed_slot
sample_count=5863
file_count=288
row_count=5863
overlap_check=passed
```

`full-writeback-records.json` 记录每条写入的来源文件、偏移、原槽长度、payload 容量、候选编码长度、终止符、补零长度和风险标签。

## ROM 验证

命令：

```text
.\tools\ndstool.exe -i rom\narutorpg3_chs_full_writeback_test.nds
```

摘要：

```text
Game title=NARUTORPG3
Game code=ANTJ
Header CRC=OK
Banner CRC=OK
ARM9 footer found
```

## DeSmuME MCP 启动检查

加载：

```text
rom/narutorpg3_chs_full_writeback_test.nds
```

状态：

```text
running=1 ARM9_PC=0x0200821C ARM7_PC=0x038042B0
```

截图：

```text
plan/cache/text-writeback-smoke/desmume-full-writeback-boot.bmp
plan/cache/text-writeback-smoke/desmume-full-writeback-boot.png
```

结论：全量写回 ROM 可被 DeSmuME MCP 加载并运行到初始画面；后续仍需人工或自动流程测试具体中文显示。

## 字节抽查

`msg/btl/000.m` offset `0x0E`：

```text
F0 40 F0 41 F0 42 F0 43 03 01 02 00 F0 44 F0 45 ...
```

`param/item_data.dat` offset `0x3C60`：

```text
F0 41 F0 42 F1 E0 F6 44 00 00 00 00
```

## 待测试风险

- 中文扩展码端序仍需通过实际显示确认。
- ASCII 行本轮按单字节候选写回，可能在部分路径显示不一致。
- padding 本轮统一剥离后补 `00`，如果个别资源不是 C 字符串式终止，可能影响显示或解析。
- 全量写回没有做文本池扩容；虽然固定槽容量未超限，但排版和换行仍需游戏内验证。

## 后续定位：标题菜单不属于本次全量写回范围

更新时间：2026-06-02

Windows 窗口截图确认红色标题菜单仍显示日文选项。定位后确认：

- 标题菜单选项硬编码在 `overlay/overlay_0004.bin`，不是 `data/text/msg/...` 普通消息文件。
- `full-writeback-records.json` 中 overlay 写回记录为 0。
- 本次 5863 条全量写回覆盖的是 `text/writeback/encoded_preview.tsv` 中的候选，未覆盖 overlay 字符串。

已构建单独探针 ROM 供验证菜单绘制链路：

```text
rom/narutorpg3_chs_full_writeback_menu_overlay_probe.nds
plan/cache/text-writeback-smoke/menu-overlay-probe-records.json
hack/标题菜单文本来源.md
```
