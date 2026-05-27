# 阶段缓存：按字符替换 glyph 稳定性复核

更新时间：2026-05-27

## 背景

此前 `rom/test_vram_font_char_hook_probe.nds` 和 `rom/test_vram_font_original_glyph_copy_probe.nds` 在放行后出现过：

```text
running=0 ARM9_PC=0x02089210 ARM7_PC=0x00000020
running=0 ARM9_PC=0x0208AA44 ARM7_PC=0x00000020
```

当时初步记录为“替换为自定义 glyph 数据后停机”。本轮复核发现这个判断需要修正：这些状态可以通过 `nds_resume` 继续运行，不是已确认的崩溃。

## 复核 ROM

```text
rom/test_vram_font_original_glyph_copy_probe.nds
rom/test_vram_font_char_hook_probe.nds
```

两者都由 `tools/patch_vram_font_char_hook_probe.py` 构建，均未覆盖 `rom/origin.nds`。

## 关键观察

### 原 glyph 副本版本

加载 `rom/test_vram_font_original_glyph_copy_probe.nds` 后读取：

```text
0x06882280 = 11111111 11111111 11111111 12311231 ...
0x02074180 = 11111111 11111111 11111111 12311231 ...
```

结论：`0x02074180` 中的 RAM 副本和 `0x82CD` 原始 VRAM glyph 源完全一致。

在出现 `running=0 ARM9_PC=0x02089210 ARM7_PC=0x00000020` 后执行 `nds_resume`：

```text
running=1 ARM9_PC=0x0200821C ARM7_PC=0x038042B0
```

fresh reload 后清除断点、放行运行，最终状态：

```text
running=1 ARM9_PC=0x0200821C ARM7_PC=0x038042B0
current_char=0x82E9
```

### test-pattern 版本

加载 `rom/test_vram_font_char_hook_probe.nds`，不保留断点，推进输入后 3 秒：

```text
running=1 ARM9_PC=0x01FFBC4C ARM7_PC=0x038042B0
current_char=0x8140
custom_glyph=33333333 11111111 33333333 11111111 ...
```

截图保存：

```text
plan/cache/vram-font-bypass/screens/char-hook-test-pattern-fresh.bmp
```

## 修正结论

- `0208914C` 保存当前字符码的 hook 稳定。
- `02089190` copy hook 框架稳定。
- `0x82CD -> 0x02074180` 的按字符替换已经验证可进入原复制函数。
- `0x02074180` 可以放置原 glyph 副本，也可以放置 test-pattern glyph 数据。
- 之前记录的 `running=0` 更像调试暂停/断点现场，不能作为崩溃证据。

## 后续判断

方案 A（动态 glyph 缓存）可以进入正式设计阶段。

下一步不应继续纠结“RAM glyph 源是否可读”，而应设计：

- 字符码到 glyph 数据的映射表。
- glyph 数据放在 NitroFS 文件、ARM9 扩展区或独立 overlay 的方式。
- 小型 RAM/VRAM 缓存槽结构。
- 与 1x1/1x2 mode、宽度和调色板的关系。
