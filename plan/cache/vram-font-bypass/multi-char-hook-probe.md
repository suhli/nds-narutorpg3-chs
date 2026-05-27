# 阶段缓存：多字符小表 hook 验证

更新时间：2026-05-27

## 目标

把单字符匹配扩展为最小两项小表：

```text
current_char == char_a -> R0 = glyph_a_addr
current_char == char_b -> R0 = glyph_b_addr
otherwise keep original R0
```

这一步用于验证动态 glyph 缓存正式实现前的查表分流能力。

## 新增脚本

```text
tools/patch_vram_font_multi_char_hook_probe.py
```

默认构建：

```text
char_a=0x82CD -> glyph_a=0x020741A0
char_b=0x82DF -> glyph_b=0x020741E0
current_char=0x02074480
```

脚本支持参数：

```text
--char-a
--char-b
--work
--output
```

语法检查：

```text
python -B -c "compile(...)"
syntax ok
```

说明：`python -m py_compile` 因 `tools/__pycache__` 权限拒绝不能写 `.pyc`，所以本轮使用不写缓存的 `compile(...)` 检查语法。

## 构建产物

默认两字符版本：

```text
rom/test_vram_font_multi_char_hook_probe.nds
rom/unpacked/vram_font_multi_char_hook_probe/
```

运行时可触发字符版本：

```text
rom/test_vram_font_multi_char_8140_probe.nds
rom/unpacked/vram_font_multi_char_8140_probe/
```

构建命令：

```text
.\.venv\Scripts\python.exe tools\patch_vram_font_multi_char_hook_probe.py --work rom/unpacked/vram_font_multi_char_8140_probe --output rom/test_vram_font_multi_char_8140_probe.nds --char-a 0x8140 --char-b 0x82CD
```

所有输出均为新 ROM，未覆盖 `rom/origin.nds`。

## Patch 布局

```text
0208914C -> BL 0207411C
02089190 -> BL 02074140

0207411C save-current-char hook
02074140 two-entry copy hook
020741A0 glyph A
020741E0 glyph B
02074480 current_char
```

原始 ARM9 空洞从 `0x0207411C` 开始连续 `0x380` 字节可用，本轮使用范围仍在该空洞内。

## MCP 验证

ROM：

```text
rom/test_vram_font_multi_char_8140_probe.nds
```

断点：

```text
ARM9 execute 020087BC
```

命中结果：

```text
current_char=00008140
R0=0x020741A0
R1=0x02292A40
```

这证明小表第一项已经能把实际运行中出现的字符 `0x8140` 分流到独立 RAM glyph 源地址。

清除断点并 `nds_resume` 后：

```text
running=1 ARM9_PC=0x0200821C ARM7_PC=0x038042B0
```

截图：

```text
plan/cache/vram-font-bypass/screens/multi-char-8140-verified.bmp
```

## 限制

本轮输入路径没有触发默认版本里的 `0x82CD/0x82DF` 两个字符，因此默认双字符版本只完成静态检查和 ROM 构建。运行时断点已验证 `0x8140` 这一项；下一轮需要找到稳定触发 `0x82CD/0x82DF` 的 UI/文本路径，或改用已知会连续出现的两个字符继续复核第二项。

## 下一步

- 找到能稳定触发第二个字符的文本路径。
- 把两项硬编码比较改为循环查表。
- 确认查表代码预算和寄存器保存策略。
- 设计中文 glyph 文件预加载到 RAM 的流程，避免在绘制路径中同步读 NitroFS。
