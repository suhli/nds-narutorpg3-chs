# 阶段缓存：按字符码替换 glyph 源验证

## 当前阶段

阶段：按当前字符码替换 glyph 源。

状态：已完成核心验证，稳定性范围已缩小。

## 目标

把第一版“按固定 glyph 源地址替换”升级为“按当前字符码替换”。

## 构建产物

脚本：

```text
tools/patch_vram_font_char_hook_probe.py
```

测试 ROM：

```text
rom/test_vram_font_char_hook_probe.nds
```

工作目录：

```text
rom/unpacked/vram_font_char_hook_probe/
```

## Patch 点

保存当前字符码：

```text
0208914C: mov r6, r1
```

改为：

```text
0208914C: bl 0207411C
```

`0207411C` hook 行为：

```text
mov r6, r1
*(u32*)0x020741C0 = r1
return 02089150
```

复制前替换 glyph 源：

```text
02089190: bl 020087BC
```

改为：

```text
02089190: bl 02074140
```

`02074140` hook 行为：

```text
if (*(u32*)0x020741C0 == 0x82CD):
    R0 = 0x02074180
b 020087BC
```

## MCP 验证证据

保存字符 hook 命中：

```text
PC=0x0207411C
R1=0x00008140
LR=0x02089150
```

复制函数样本：

```text
i=0 current=0x8140 R0=0x06881C00
i=1 current=0x8140 R0=0x06881C00
i=2 current=0x8140 R0=0x06881C00
i=3 current=0x8140 R0=0x06881C00
i=4 current=0x82CD R0=0x02074180
```

最终命中时：

```text
PC=0x020087BC
R0=0x02074180
R1=0x02292B40
R2=0x00000040
LR=0x02089194
current_char=0x000082CD
```

结论：

- 当前字符码可以在 `0208914C` 保存。
- `02089190` 的 copy hook 可以读取该字符码。
- `R0` 可以按字符码替换为自定义 glyph 数据地址。

## 稳定性风险

放行运行后，模拟器停在：

```text
ARM9_PC=0x0208AA44
ARM7_PC=0x00000020
```

无断点残留。截图仍停留在标题画面。

初步判断：

- “按字符码替换 R0”本身已验证成立。
- 第二版 hook 仍需稳定性复核，尤其是保存字符 hook、copy hook 是否破坏寄存器/状态，或自定义 glyph 数据是否触发后续路径异常。

## 下一步

- 复核 `0207411C` 和 `02074140` 两个 hook 的寄存器保存范围。
- 试一个“按字符码匹配但仍返回原 glyph 源”的 no-op 版本，排除保存字符 hook 本身的风险。
- 再试“按字符码替换为原 glyph 数据拷贝”的版本，排除自定义 glyph 数据格式风险。

## 稳定性复核 1：只保存字符码

测试 ROM：

```text
rom/test_vram_font_save_char_noop_probe.nds
```

脚本：

```text
tools/patch_vram_font_save_char_noop_probe.py
```

行为：

- 只 patch `0208914C -> 0207411C`。
- 保存当前字符码到 `0x02074140`。
- 不 patch `02089190`。

验证结果：

```text
0207411C 命中时 R1=0x8140
放行后 current_char=0x82E9
运行 3.5 秒后 running=1
ARM9_PC=0x0200821C
ARM7_PC=0x038042B0
```

结论：

```text
保存当前字符码这一步稳定。
```

## 稳定性复核 2：copy hook no-op

测试 ROM：

```text
rom/test_vram_font_copy_noop_probe.nds
```

构建命令：

```text
python tools/patch_vram_font_char_hook_probe.py --work rom/unpacked/vram_font_copy_noop_probe --output rom/test_vram_font_copy_noop_probe.nds --match-char 0xFFFF
```

行为：

- patch `0208914C -> 0207411C` 保存字符码。
- patch `02089190 -> 02074140` 进入 copy hook。
- `match-char=0xFFFF`，实际不会替换 `R0`。

验证结果：

```text
02074140 命中时：
current_char=0x8140
R0=0x06881C00
R1=0x02292A40
R2=0x00000040

放行后：
current_char=0x82E9
running=1
ARM9_PC=0x0200821C
ARM7_PC=0x038042B0
```

结论：

```text
copy hook 框架本身稳定。
不稳定点集中在“命中字符后替换为 0x02074180 自定义 glyph 数据”。
```

## 下一步修正

下一轮优先构建：

```text
match 0x82CD，但 0x02074180 放的是原 0x82CD glyph 的完整副本。
```

用途：

- 如果稳定，说明自定义 glyph 数据格式/内容有问题。
- 如果仍不稳定，说明“替换非空白字符的源地址到 ARM9 RAM”还需要进一步处理。
