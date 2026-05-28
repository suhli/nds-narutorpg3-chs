# 阶段缓存：NitroFS 文件预加载到 RAM 验证

更新时间：2026-05-27

## 目标

把测试用的映射表和 glyph 数据从 ARM9 空洞迁移到 NitroFS 文件，并在字体初始化阶段加载到普通 RAM。

最终绘制路径仍保持：

```text
current_char -> lookup table in RAM -> R0 = RAM glyph address -> 020087BC
```

## 新增脚本

```text
tools/patch_vram_font_file_preload_probe.py
```

输出 ROM：

```text
rom/test_vram_font_file_preload_probe.nds
```

工作目录：

```text
rom/unpacked/vram_font_file_preload_probe_v2/
```

说明：首次构建失败后留下了 `rom/unpacked/vram_font_file_preload_probe/`，清理时遇到大量解包文件权限拒绝；后续改用 `_v2` 工作目录，不影响原版 ROM 和当前有效产物。

## 新增 NitroFS 文件

```text
font/chs_probe.bin
```

解包路径：

```text
rom/unpacked/vram_font_file_preload_probe_v2/data/font/chs_probe.bin
```

文件大小：

```text
0xA0 bytes
```

文件结构：

```text
u32 entry_count
entry[entry_count]:
  u32 char_code
  u32 glyph_offset
glyph data:
  0x20: glyph A
  0x60: glyph B
```

当前测试数据：

```text
0x82CD -> glyph_offset 0x20
0x82DF -> glyph_offset 0x60
```

## Patch 布局

```text
020869E0 -> B 020741A0
0208914C -> BL 0207411C
02089190 -> BL 02074140

0207411C  save-current-char hook
02074140  RAM file table lookup hook
020741A0  font init tail hook, calls 0207F80C
02074240  "font/chs_probe.bin"
02074280  chs_data_ptr
02074284  chs_data_size
02074288  current_char
```

`020869E0` 原本是字体初始化函数尾部：

```text
add sp, sp, #0x20
pop {r4, pc}
```

本轮改为跳到 `020741A0`，hook 先调用原文件加载函数 `0207F80C`，再执行原尾部栈恢复。

## MCP 验证

采样命令：

```text
.\.venv\Scripts\python.exe -B tools\sample_vram_font_chars_mcp.py --rom rom\test_vram_font_file_preload_probe.nds --current-char-address 02074288 --stop-after-chars 0x82CD,0x82DF --max-samples 30 --output plan\cache\vram-font-bypass\file-preload-verify-samples.json
```

关键结果：

```text
chs_data_ptr  = 0x02282F40
chs_data_size = 0x000000A0

0x82CD -> R0=0x02282F60
0x82DF -> R0=0x02282FA0
```

其中：

```text
0x02282F60 = 0x02282F40 + 0x20
0x02282FA0 = 0x02282F40 + 0x60
```

运行时读取 `0x02282F40`：

```text
00000002 000082CD 00000020 000082DF 00000060 ...
33333333 11111111 ...
44442222 22224444 ...
```

收尾状态：

```text
running=1 ARM9_PC=0x0200821C ARM7_PC=0x038042B0
```

## 结论

已验证：

- 可以新增 NitroFS 文件作为自定义 glyph/映射表数据源。
- 可以在字体初始化阶段调用原 `0207F80C` 加载该文件。
- `0207F80C` 可以把目标指针初始为 0 的文件加载到普通 RAM，并回写实际 RAM 指针和大小。
- 绘制 hook 可以从普通 RAM 文件结构中查表，并把 `R0` 指向 RAM glyph。

这已经把动态字体方案从“ARM9 空洞测试数据”推进到“ROM 文件 -> 普通 RAM -> 绘制 hook”的链路。

## 下一步

- 把 `chs_probe.bin` 结构升级为正式 `chs_map.bin` + `chs_1x2.chr`，或保留单文件但增加 magic/version。
- 设计更接近最终用途的映射项：`char_code/mode/width/glyph_offset`。
- 决定是否在 `0208671C` 层处理中文字符，减少 `02089190` 处对 `current_char` 全局变量的依赖。
- 找 1x1 字体路径样本，确认同一 RAM 文件查表逻辑能否同时服务 1x1 和 1x2。
