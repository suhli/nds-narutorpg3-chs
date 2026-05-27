# 阶段缓存：运行时确认关键地址和数据流

## 当前阶段

阶段：运行时确认关键地址和数据流。

状态：进行中。

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
- 最小 Hook 候选仍然是 `0208671C` 或其调用点 `0208913C/0208916C`。

## 待完成

- `0208671C` 断点在当前自动运行阶段未命中。
- 后续可使用新版 MCP 输入工具推进到正文/菜单文本。
- 命中后需要记录 `r0` 字符码、`r1` mode、返回地址，以及 `0208916C` 实际复制源地址。
