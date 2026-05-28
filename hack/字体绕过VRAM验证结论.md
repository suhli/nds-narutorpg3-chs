# 字体绕过 VRAM 验证结论

更新时间：2026-05-27
状态：第二版按字符码 hook 核心验证通过，稳定性复核通过

## 1. 验证问题

要验证的关键问题：

```text
原 glyph 复制函数是否只能从 0x06880000 附近的 VRAM 字库读取？
```

结论：

```text
不是。020087BC 可以从 ARM9 RAM/代码段中的自定义 glyph 数据读取。
```

## 2. 实验 ROM

有效实验 ROM：

```text
rom/test_vram_font_hook_probe_arm9.nds
```

构建脚本：

```text
tools/patch_vram_font_hook_probe.py
```

失败实验 ROM：

```text
rom/test_vram_font_hook_probe.nds
```

失败原因：hook 追加到了 overlay_0000 的 BSS 起始区，破坏运行时数据，黑屏。

## 3. 有效 patch

修改点：

```text
02089190: bl 020087BC
```

改为：

```text
02089190: bl 0207411C
```

hook 位置：

```text
0207411C  ARM9 主程序零区
0207413C  自定义 0x40 字节测试 glyph
```

hook 逻辑：

```text
if R0 == 0x06881C00:
    R0 = 0x0207413C
b 020087BC
```

## 4. MCP 验证证据

hook 入口：

```text
PC=0x0207411C
R0=0x06881C00
R1=0x02292A40
R2=0x00000040
LR=0x02089194
```

进入原复制函数：

```text
PC=0x020087BC
R0=0x0207413C
R1=0x02292A40
R2=0x00000040
LR=0x02089194
```

自定义 glyph 数据：

```text
22222222 22222222 22222222 22222222
22222222 22222222 22222222 22222222
33333333 33333333 33333333 33333333
33333333 33333333 33333333 33333333
```

## 5. 技术判断

- `02089190` 是有效的最小 hook 点。
- `R0` 可以改为非原 VRAM 字库地址。
- 第一版动态缓存可以基于“复制前替换 `R0`”继续推进。
- 不能直接占用 overlay_0000 的 BSS 起始区放 hook。
- 后续应使用 ARM9 空洞、独立 overlay、或明确分配的 RAM 区放 hook/cache。

## 6. 下一步

- 第二版已经让 hook 能按当前字符码匹配：`0x82CD -> 0x02074180`。
- 设计 glyph cache 结构：字符码、mode、源数据地址、缓存槽。
- 决定中文 glyph 数据存放在 ROM 文件、ARM9 扩展区还是独立 overlay/NitroFS 文件。
- 继续验证 1x1 mode。

## 7. 第二版验证补充

新增测试 ROM：

```text
rom/test_vram_font_char_hook_probe.nds
```

新增脚本：

```text
tools/patch_vram_font_char_hook_probe.py
```

关键证据：

```text
i=4 current=0x82CD R0=0x02074180
PC=0x020087BC
R1=0x02292B40
R2=0x00000040
```

这证明后续可以走：

```text
当前字符码 -> 查自定义映射 -> 返回/替换 glyph 源地址
```

稳定性风险：

```text
此前放行后出现过 `running=0 ARM9_PC=0x0208AA44 / ARM7_PC=0x00000020`，复核后确认可通过 `nds_resume` 继续运行，不能作为崩溃证据。
```

no-op 复核结论：

```text
保存字符 hook 稳定。
copy hook 框架稳定。
不稳定点集中在 0x82CD 命中后替换到自定义 glyph 数据。
```

`0x82CD 替换到原 glyph 副本` 的版本已经复核：RAM 副本与原 VRAM glyph 一致，清除断点后可继续运行。因此下一步进入动态 glyph 缓存设计。

## 8. RAM 预加载压力结论

新增脚本：

```text
tools/run_font_preload_size_sweep.py
```

已经验证 `font/chs_probe.bin` 扩大后的加载行为：

```text
1008K 以内仍可取得文本绘制采样。
1024K 开始在文本流程失稳。
1392K 起 chs_data_ptr=0，整文件连续分配失败。
```

因此“字库放普通 RAM”也不能理解为“完整中文字模整包常驻 RAM”。可行方向应是：

```text
map/header 常驻
glyph 数据分页或分块
绘制时按需准备 glyph
VRAM 只保留当前画面缓存
```
