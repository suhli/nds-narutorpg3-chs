# 阶段缓存：表驱动 glyph 查找 hook 验证

更新时间：2026-05-27

## 目标

把此前的两项硬编码比较：

```text
if current_char == 0x82CD: R0 = glyph_a
if current_char == 0x82DF: R0 = glyph_b
```

改为表驱动循环：

```text
for entry in lookup_table:
    if entry.char_code == current_char:
        R0 = entry.glyph_addr
        break
```

## 新增脚本

```text
tools/patch_vram_font_table_hook_probe.py
```

输出 ROM：

```text
rom/test_vram_font_table_hook_probe.nds
rom/unpacked/vram_font_table_hook_probe/
```

构建命令：

```text
.\.venv\Scripts\python.exe tools\patch_vram_font_table_hook_probe.py
```

所有输出均为新 ROM，未覆盖 `rom/origin.nds`。

## Patch 布局

```text
0208914C -> BL 0207411C
02089190 -> BL 02074140

0207411C  save-current-char hook
02074140  table lookup copy hook
02074190  lookup table
02074200  glyph A
02074240  glyph B
02074480  current_char
```

表项格式：

```text
u32 char_code
u32 glyph_addr
```

当前测试表：

```text
0x82CD -> 0x02074200
0x82DF -> 0x02074240
```

## 反汇编检查

`02074140` 反汇编确认已经是循环查表：

```text
02074140: push {r2, r3, ip, lr}
02074144: ldr  r3, [pc, #0x34]
02074148: ldr  r3, [r3]
0207414C: ldr  ip, [pc, #0x30]
02074150: ldr  r2, [pc, #0x30]
02074154: cmp  r2, #0
02074158: beq  done
0207415C: ldr  lr, [ip], #4
02074160: cmp  r3, lr
02074164: ldreq r0, [ip]
02074168: beq  done
0207416C: add  ip, ip, #4
02074170: subs r2, r2, #1
02074174: b    loop
02074178: pop  {r2, r3, ip, lr}
0207417C: b    020087BC
```

`r2/r3/ip/lr` 在进入原复制函数前恢复，`R0` 在命中时被替换为表内 glyph 地址。

## MCP 验证

命令：

```text
.\.venv\Scripts\python.exe -B tools\sample_vram_font_chars_mcp.py --rom rom\test_vram_font_table_hook_probe.nds --current-char-address 02074480 --stop-after-chars 0x82CD,0x82DF --max-samples 30 --output plan\cache\vram-font-bypass\table-lookup-verify-samples.json
```

关键结果：

```text
index 4  current_char=0x82CD  R0=0x02074200  R1=0x02292B40
index 6  current_char=0x82DF  R0=0x02074240  R1=0x02292BC0
```

收尾状态：

```text
running=1 ARM9_PC=0x0200821C ARM7_PC=0x038042B0
```

## 结论

表驱动查找原型成立。下一步可以把测试表从 ARM9 空洞迁移为“预加载到普通 RAM 的映射表”，并把 glyph 数据来源从 ARM9 空洞迁移到预加载 glyph 仓库。
