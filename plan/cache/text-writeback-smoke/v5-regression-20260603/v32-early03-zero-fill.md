# v32 固定长度早停 03 + 00 填充候选

## 背景

v29 的变长压缩会让所有对话卡死，说明 message 文件内部长度和后续 offset 不能改变。v30 改成固定长度早停 `03 00` 后用全角空格填充，但用户继续提出可以尝试用 `00 00` 填充。

v32 因此保持 v30 的固定长度策略，只把 `03 00` 后的填充从全角空格改为 `00`。

## 写回策略

新增显式开关：

```text
--early-message-terminator-zero-fill
```

该开关与下面两个策略互斥：

```text
--compact-message-terminators
--early-message-terminator-fullwidth-fill
```

普通 `03 00` message 的写回形态：

```text
prefix + encoded_text + 03 00 + 00 padding to original slot length
```

不参与该策略的结构：

- 固定 `CTRL_0000` 子槽位记录。
- NUL4 描述表。
- 参数表。
- overlay 固定布局。
- 特殊 scene-tail message。

## 同步修复

- `trim_blank_ctrl0001_pages()` 现在会在删除空白 `{CTRL_0001}` 前判断是否会把相邻控制符拼成新的裸字节 `03 00`。如果会生成新的结束符，就保留 `{CTRL_0001}` 作为结构分隔。
- `zh_txt_0d5c73a4_000484_0016` 和 `zh_txt_0d5c73a4_00058A_0019` 加入可翻译前缀列表，避免正文重复携带 `{CTRL_0103}{CTRL_0000}{CTRL_0003}{CTRL_0002}` 这一类前缀控制序列。
- 结构审计新增裸字节 `03 00` 内部位置检查，只允许 replacement 中已有的内部 `03 00` 数量不超过 raw 原始数量。

## 候选 ROM

```text
rom/narutorpg3_chs_patcher_v32_early03_zero_fill.nds
SHA256 EFC2B8A27B1213FA5189BC159C006822BA35D3AA03DB184A543776BA188996EF
```

构建目录：

```text
patcher/work/build_20260612_113000
```

记录文件：

```text
plan/cache/text-writeback-smoke/v5-regression-20260603/v32-early03-zero-fill-records.json
plan/cache/text-writeback-smoke/v5-regression-20260603/v32-early03-zero-fill-structural-audit.json
plan/cache/text-writeback-smoke/v5-regression-20260603/v32-early03-zero-fill-byte-terminator-audit.json
```

## 静态验证

- Python AST 语法检查通过，覆盖 7 个改动脚本。
- `ndstool -i`：Header CRC OK / Banner CRC OK。
- 写回记录 `text_writeback.row_count=5858`，`menu_writeback.row_count=289`。
- `early_03_zero_fill_row_count=3179`，`early_03_zero_fill_bytes=70348`。
- 结构审计 `risk_rows=0`，`blank_ctrl0001_page_row_count=0`。
- 结构审计中 replacement 内部 `03 00` 行数为 3，raw 原始内部 `03 00` 行数也为 3，没有新增内部结束符。
- 实际工作目录字节审计 `checked=5858`，`risk_count=0`。
- 实际早停零填充行 `early03_zero_rows=3179`。
- 教程/战斗教程类 `msg/btl` 检查 73 行，其中普通早停零填充 36 行。
- 所有早停 `03 00` 后的剩余字节均为 `00`。
- 文本和菜单缺字为 0，字体仅保留既有占位符 `U+E0FD`。

## 控制符结论

- `03 00` 在普通 message 末尾是结束符；但 `{CTRL_0003}` 在某些原始控制序列中也是合法控制字，因此不能简单禁止所有内部裸字节 `03 00`，必须和 raw 原始数量对比。
- `{CTRL_0001}` 是换页/换行类控制符，也可能作为控制序列分隔符。删除它如果会拼出新的 `03 00`，就必须保留。
- `{CTRL_0000}` 是固定子槽位或字段分隔结构，相关记录继续按原始子槽位偏移写回。

## 运行时验证

本轮未使用 DeSmuME/MCP。运行时显示、是否仍有空行或卡死，继续由用户手动测试。
