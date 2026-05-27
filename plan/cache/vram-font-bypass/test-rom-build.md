# 阶段缓存：构建最小实验 ROM

## 当前阶段

阶段：构建最小实验 ROM。

状态：已完成。

## 构建脚本

新增脚本：

```text
tools/patch_vram_font_hook_probe.py
```

脚本行为：

- 从 `rom/unpacked/origin/` 复制一份工作目录。
- 修改 `overlay_0000.bin` 中 `02089190` 的 `BL` 目标。
- 将 hook 代码和测试 glyph 写入 `arm9.bin` 的零区 `0x0207411C`。
- 使用 `tools/ndstool.exe` 打包为新的测试 ROM。
- 不覆盖 `rom/origin.nds`。

## 成功输出

```text
work = rom/unpacked/vram_font_hook_probe_arm9
rom  = rom/test_vram_font_hook_probe_arm9.nds
hook = 0x0207411C
custom_glyph = 0x0207413C
```

构建后执行：

```text
tools/ndstool.exe -f rom/test_vram_font_hook_probe_arm9.nds
```

`ndstool -i` 检查结果：

```text
Game title  NARUTORPG3
Game code   ANTJ
Header CRC  OK
```

## 失败尝试记录

第一版曾尝试：

```text
rom/test_vram_font_hook_probe.nds
rom/unpacked/vram_font_hook_probe/
```

做法是把 hook 追加到 `overlay_0000.bin` 尾部并缩小 overlay BSS。

结果：

- ROM 可被 ndstool 读取。
- 模拟器黑屏。
- 运行时 `0x020AEB80` 不是 hook 字节。

判断：

- `0x020AEB80` 是 overlay_0000 原 BSS 起始区域。
- 直接占用这里会破坏运行时数据。
- 后续不要使用这个方案。

## 验证用截图

- `plan/cache/vram-font-bypass/screens/probe-arm9-000-boot.bmp`
- `plan/cache/vram-font-bypass/screens/probe-arm9-001-after-start.bmp`
- `plan/cache/vram-font-bypass/screens/probe-arm9-010-after-hook.bmp`

