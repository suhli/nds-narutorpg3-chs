# 阶段缓存：模拟器验证和方案判定

## 当前阶段

阶段：模拟器验证和方案判定。

状态：进行中。

## 已完成验证

- 使用 DeSmuME MCP 加载 `rom/test_vram_font_hook_probe_arm9.nds`。
- ROM 可启动到标题动画。
- hook 入口 `0x0207411C` 成功命中。
- 原复制函数 `0x020087BC` 入口成功命中。
- 已确认 hook 将 `R0` 从原 VRAM glyph 地址替换为 ARM9 自定义 glyph 地址。
- 使用 DeSmuME MCP 加载 `rom/test_vram_font_char_hook_probe.nds`。
- 已确认 `0208914C` 可保存当前字符码。
- 已确认 `02089190` hook 可按当前字符码 `0x82CD` 将 `R0` 替换为 `0x02074180`。

## 关键证据

```text
hook entry:
PC=0x0207411C
R0=0x06881C00
R1=0x02292A40
R2=0x00000040
LR=0x02089194

copy entry:
PC=0x020087BC
R0=0x0207413C
R1=0x02292A40
R2=0x00000040
LR=0x02089194
```

## 判定

方案 A（动态 glyph 缓存）继续作为主线。

原因：

- 已确认 glyph 源不必固定为原 VRAM 字库地址。
- 在 `02089190` 前替换 `R0` 就能把源切到自定义数据。
- 这可以扩展为“按需准备 glyph，再把 `R0` 指向缓存”的方案。

## 未完成

- 第二版按字符码替换到自定义 glyph 后，放行运行出现停机状态：`ARM9_PC=0x0208AA44`，`ARM7_PC=0x00000020`。
- 还没有验证 1x1 mode。
- 还没有实现字符码到中文 glyph 的动态映射。
- 还没有设计缓存淘汰和同屏复用策略。

## 下一步

- 优先做 no-op 版本验证稳定性：保存当前字符码，但不替换 `R0`。
- 再做“按字符码匹配但替换为原 glyph 数据副本”的版本，排除自定义 glyph 格式风险。
- 设计中文 glyph 数据文件格式和加载位置。

## 第二版补充证据

```text
i=4 current=0x82CD R0=0x02074180

PC=0x020087BC
R0=0x02074180
R1=0x02292B40
R2=0x00000040
LR=0x02089194
current_char=0x000082CD
```

## 稳定性复核补充

保存字符码 no-op：

```text
rom/test_vram_font_save_char_noop_probe.nds
0207411C 命中，R1=0x8140
放行后 current_char=0x82E9
running=1
```

copy hook no-op：

```text
rom/test_vram_font_copy_noop_probe.nds
02074140 命中，current_char=0x8140
R0=0x06881C00
放行后 current_char=0x82E9
running=1
```

判定：

```text
保存字符 hook 稳定。
copy hook 框架稳定。
风险集中在命中字符后替换为自定义 glyph 数据这一步。
```

## 2026-05-27 复核修正

此前记录的 `running=0 ARM9_PC=0x02089210 / ARM7_PC=0x00000020` 复核后不是崩溃证据。执行 `nds_resume` 后可继续运行到：

```text
running=1 ARM9_PC=0x0200821C ARM7_PC=0x038042B0
```

`rom/test_vram_font_original_glyph_copy_probe.nds` 中，`0x02074180` 的原 glyph 副本与 `0x06882280` 一致；`rom/test_vram_font_char_hook_probe.nds` 的 test-pattern 版本也能在清除断点后继续运行。阶段结论修正为：动态 glyph 缓存路线可进入正式设计。
