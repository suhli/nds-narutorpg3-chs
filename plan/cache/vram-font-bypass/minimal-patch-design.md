# 阶段缓存：最小可验证 patch 设计

## 当前阶段

阶段：设计最小可验证 patch。

状态：已完成。

## 目标

先不实现完整中文动态缓存，只验证一个核心能力：

- 原绘制路径在 `02089190` 调用 glyph 复制函数。
- 若在 `02089190` 前把 `R0` 从原 VRAM glyph 地址替换成自定义地址，复制函数仍能正常取字形。
- 这能证明后续字形源可以从“按需准备的缓存/数据区”来，而不是只能来自原始全量 VRAM 字库。

## 已确认输入输出

`02089190` 命中时：

```text
R0 = glyph source
R1 = glyph destination buffer
R2 = copy size
```

样本：

```text
R0=0x06881C00
R1=0x02292A40
R2=0x00000040
```

上游：

- `0208671C` 输入 `R0=字符编码`、`R1=mode`。
- `0208671C` 返回 `R0=glyph source`。
- 当前样本为 `mode=1`，单位大小 `0x40`。

## 第一版 Hook 点

替换位置：

```text
02089190: bl 020087BC
```

替换为：

```text
02089190: bl hook
```

hook 逻辑：

```text
push {r3, lr}
if R0 == 0x06881C00:
    R0 = custom_glyph_data
pop {r3, lr}
b 020087BC
```

解释：

- `0x06881C00` 是 `0x8140` 在 1x2 表中的 glyph 源地址。
- 只替换这个 glyph，降低验证范围。
- `R1/R2` 不改，保留原绘制函数的目标缓存和大小。
- 用 `b 020087BC` 尾调用原复制函数，保留原本 `LR=02089194` 的返回行为。

## Hook 放置位置（修正后）

最初尝试将 hook 追加到 `overlay_0000.bin` 尾部，并修改 `y9.bin` 的 overlay size/bss size。

该方案会占用 overlay_0000 原本的 BSS 起始区，测试 ROM 黑屏，不能使用。

修正方案：hook 放入 ARM9 主程序中已加载的空洞。

```text
arm9_base = 0x02000000
hook_addr = 0x0207411C
available_zero_run = 0x0207411C-0x0207449C
```

可行方案：

- `overlay_0000.bin` 只替换 `02089190` 的 `BL` 目标。
- hook 代码和测试 glyph 写入 `arm9.bin` 的零区 `0x0207411C`。
- 不改 `y9.bin`，不改变 overlay_0000 的 size/bss。

第一版建议地址：

```text
hook_addr = 0x0207411C
custom_glyph_data = 0x0207413C
```

## 第一版验证 glyph

使用 64 字节测试 glyph，匹配当前 `mode=1` 的复制大小 `0x40`。

建议先使用明显可见的填充/棋盘数据，替换 `0x8140` 对应的 glyph。

如果画面中 `0x8140` 是空白/间隔字符，替换后应能看到明显块状痕迹，便于确认 hook 生效。

## 风险

- 如果 `020087BC` 对源地址有 VRAM 特殊假设，RAM 源地址可能失败；这正是本实验要验证的点。
- 当前只覆盖 `mode=1`，不代表 1x1 路径已经可用。
- `0x8140` 可能是空白字符，替换后视觉结果取决于实际菜单文本位置。
- overlay 追加需要修改 `y9.bin`，必须只在测试解包目录中进行，不能覆盖原始解包目录和 `rom/origin.nds`。

## 验证输出

- 新测试 ROM：`rom/test_vram_font_hook_probe_arm9.nds`
- 构建记录：`plan/cache/vram-font-bypass/test-rom-build.md`
- 截图记录：`plan/cache/vram-font-bypass/screens/`

## 验证结论

已用 DeSmuME MCP 确认：

- `02089190` 已跳转到 `0x0207411C`。
- hook 入口 `R0=0x06881C00`。
- 进入原复制函数 `020087BC` 时，`R0=0x0207413C`。
- `R1/R2` 保持原目标缓存和 `0x40` 复制大小。

这证明 glyph 源地址可以被替换到 ARM9 RAM/代码段中的自定义 glyph 数据。
