# 阶段缓存：运行时确认关键地址和数据流

## 当前阶段

阶段：运行时确认关键地址和数据流。

状态：已完成。

## 目标

- 用 DeSmuME MCP 验证字体初始化入口是否真实执行。
- 读取 `DAT_020B73E0` 运行时字段。
- 确认 `.chr/.tbl/.plt` 的实际加载地址。
- 尝试在正文绘制路径命中 `0208671C`。

## 已完成

- 已启动 `tools/desmume.exe --mcp`。
- 已通过 HTTP MCP 连接 `http://127.0.0.1:8765/`。
- 已加载 `rom/origin.nds`，未修改 ROM。
- 已命中 `ARM9 execute 0x02086870`。
- 已继续运行到 `ARM9 execute 0x020869C4`。
- 已读取并解释 `DAT_020B73E0`。
- 已确认 `font_1x1.tbl` 和 `font_1x2.tbl` 也位于 VRAM。
- 已写入 `hack/字体运行时观察.md`。
- 已验证新版 DeSmuME MCP 增加按键、触摸、释放全部和截图工具，详见 `plan/cache/vram-font-bypass/desmume-mcp-update.md`。
- 已使用新版 MCP 输入能力从标题推进到文本绘制路径。
- 已动态命中 `0208913C`、`0208671C`、`02089170`、`02089190`。
- 已确认 `0208671C` 输入输出和 `02089190` glyph 复制参数。

## 关键运行时值

```text
DAT_020B73E0:
+0x00 0x06880000 font_1x1.chr
+0x04 0x06881C00 font_1x2.chr
+0x08 0x02282EA0 font.plt
+0x0C 0x00000004 palette count
+0x20 0x0688E6C0 font_1x1.tbl
+0x24 0x000000E0 font_1x1.tbl item count
+0x28 0x0688EA40 font_1x2.tbl
+0x2C 0x0000032B font_1x2.tbl item count
```

## 结论

- 原字体系统不是只把 `.chr` 放入 VRAM，`.tbl` 也进入同一片 VRAM 字体区域。
- 中文化不能只考虑字模容量，字符映射表容量也可能成为 VRAM 压力来源。
- 最小 Hook 候选为 `0208671C` 或 `02089190`。第一版验证更适合先选 `02089190`，因为它直接处在 glyph 复制前。

## 运行时样本

```text
0208671C input:
R0=0x8140
R1=0x00000001
LR=0x02089170

02089170 return:
R0=0x06881C00
R1=0x00000040

02089190 copy:
R0=0x06881C00
R1=0x02292A40
R2=0x00000040
```

连续样本均为 `mode=1`：

```text
0x8140 -> index 0  -> 0x06881C00
0x82CD -> index 26 -> 0x06882280
0x82B6 -> index 62 -> 0x06882B80
0x82DF -> index 34 -> 0x06882480
0x82A9 -> index 6  -> 0x06881D80
0x82E7 -> index 39 -> 0x068825C0
```

## 产物

- `hack/字体运行时观察.md`
- `plan/cache/vram-font-bypass/screens/runtime-000-loaded.bmp`
- `plan/cache/vram-font-bypass/screens/runtime-001-after-start.bmp`
- `plan/cache/vram-font-bypass/screens/runtime-002-after-a.bmp`
- `plan/cache/vram-font-bypass/screens/runtime-009-after-samples.bmp`

## 后续

- 进入 `minimal-patch-design` 阶段。
- 先设计最小 patch，验证能在 `02089190` 前替换 glyph 源地址。
- 1x1 路径仍需后续验证，但不阻塞第一版 1x2 菜单/标题文本验证。
