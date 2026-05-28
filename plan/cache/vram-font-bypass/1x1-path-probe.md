# 阶段缓存：1x1 字体路径验证

更新时间：2026-05-28

## 目标

确认 `mode=0` / 1x1 字体是否复用当前已验证的绘制链路：

```text
0208913C -> 0208671C -> 02089190 -> 020087BC
```

并验证 `02089190` 前的 RAM glyph 替换 hook 是否也能服务 `R2=0x20` 的 1x1 字形复制。

## 采样 ROM

no-op 基线 ROM：

```text
rom/test_vram_font_copy_noop_probe.nds
```

1x1 替换测试 ROM：

```text
rom/test_vram_font_file_preload_1x1_probe.nds
```

工作目录：

```text
rom/unpacked/vram_font_file_preload_1x1_probe/
```

构建方式：

```text
tools/patch_vram_font_file_preload_probe.py
--work rom/unpacked/vram_font_file_preload_1x1_probe
--output rom/test_vram_font_file_preload_1x1_probe.nds
--char-a 0x82A2
--char-b 0x82BD
```

新增 NitroFS 测试文件仍为：

```text
font/chs_probe.bin
```

映射：

```text
0x82A2 -> offset 0x20
0x82BD -> offset 0x60
```

## 基线采样

输出：

```text
plan/cache/vram-font-bypass/1x1-noop-samples.json
```

no-op ROM 中已采到 `R2=0x20`：

```text
index=28 current_char=0x8140 R0=0x06880000 R1=0x06894000 R2=0x20
index=76 current_char=0x8140 R0=0x06880000 R1=0x06894BE0 R2=0x20
```

判断：

- `R2=0x20` 对应 1x1 字体复制。
- `R0` 位于 `0x06880000` 起始的 `font_1x1.chr` VRAM 区。
- `LR=0x02089194`，说明 1x1 同样从 `02089190` 调用 `020087BC`。

## RAM glyph 替换采样

输出：

```text
plan/cache/vram-font-bypass/1x1-file-preload-samples.json
```

总样本：

```text
R2=0x40: 87 samples
R2=0x20: 53 samples
```

关键 1x1 命中：

```text
index=114 current_char=0x82BD R0=0x02282FA0 R1=0x06895220 R2=0x20
index=115 current_char=0x82A2 R0=0x02282F60 R1=0x06895240 R2=0x20
index=119 current_char=0x82A2 R0=0x02282F60 R1=0x068952C0 R2=0x20
```

其中：

```text
0x02282F60 = chs_data_ptr + 0x20
0x02282FA0 = chs_data_ptr + 0x60
```

收尾状态：

```text
running=1 ARM9_PC=0x0208FF14 ARM7_PC=0x038042B0
```

## 结论

已确认：

- 1x1 与 1x2 复用同一个 `02089190 -> 020087BC` copy 点。
- 1x1 复制大小为 `0x20`，1x2 复制大小为 `0x40`。
- 1x1 原始 glyph 源位于 `font_1x1.chr` VRAM 区 `0x06880000` 起。
- 当前 `02089190` 前替换 `R0` 的方案同样能把 1x1 glyph 源切到普通 RAM。

重要约束：

当前 probe 只按 `char_code` 查表，不区分字体模式。因此 `0x82A2` 在 1x2 样本中也被替换：

```text
index=18 current_char=0x82A2 R0=0x02282F60 R2=0x40
```

正式格式不能只用 `char_code` 作为唯一 key，需要至少包含：

```text
char_code
mode 或 glyph_size
glyph_offset
width/flags
```

否则同一个字符在 1x1 和 1x2 中需要不同字模时会互相污染。

## 下一步

正式化文件格式时应把 map 拆成两种可选结构：

```text
方案 1：两个 map
chs_1x1.map + chs_1x1.chunk
chs_1x2.map + chs_1x2.chunk

方案 2：单 map 带 mode
entry { char_code, mode, width_flags, chunk_id, glyph_offset }
```

考虑到早期 hook 代码空间有限，下一步建议先做方案 1，用两个 map 简化运行时查找。
