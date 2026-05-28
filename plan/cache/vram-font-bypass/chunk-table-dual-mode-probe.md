# 阶段缓存：chunk table dual-mode 原型

## 背景

`chunk-table-dual-slot-probe` 已验证 1x2 双 resident slot 可以消除 chunk0/chunk1 来回覆盖的问题，但该 probe 为控制尺寸只接管 `R2=0x40`。本轮补齐同一 copy hook 同时处理 `R2=0x20` 与 `R2=0x40` 的原型，重点验证 1x1/1x2 不再因同一字符码互相 fallback/missing 或命中错误 glyph。

## 新增产物

```text
tools/patch_vram_font_chunk_table_dual_mode_probe.py
rom/test_vram_font_chunk_table_dual_mode_probe.nds
plan/cache/vram-font-bypass/chunk-table-dual-mode-samples.json
plan/cache/vram-font-bypass/chunk-table-dual-mode-long-samples.json
```

ROM 校验：

```text
tools/ndstool.exe -i rom/test_vram_font_chunk_table_dual_mode_probe.nds
Header CRC OK
Banner CRC OK
```

脚本静态语法检查使用 `compile(...)` 通过；直接 `py_compile` 因 `tools/__pycache__` 目标 pyc 重命名权限失败，未作为脚本语法失败处理。

## 代码区布局

```text
0x02074140  copy trampoline, size=0x4
0x02073D64  copy hook body, size=0xE8
0x020743E4  consume hook, size=0xB8
0x0207411C  extended payload, size=0x380
```

状态区：

```text
0x020743C4  miss_flag
0x020743C8  miss_char
0x020743CC  miss_chunk_id
0x020743D0  miss_mode
0x020743D4  resident_1x1_chunk_id
0x020743D8  resident_1x2_slot0_chunk_id
0x020743DC  resident_1x2_slot1_chunk_id
0x020743E0  resident_1x2_next_slot
```

运行时指针样本：

```text
1x1_map_ptr   = 0x02282F80 size=0x50
1x1_chunk_ptr = 0x02283000 size=0xA0
1x2_map_ptr   = 0x022830C0 size=0x70
1x2_chunk_ptr = 0x02284AE0 size=0x3A0
```

## 文件结构

`chs_1x1.chunk`：

```text
0x000  CHCK header
0x020  fallback glyph
0x040  0x8140 1x1 glyph, data=41144114
0x060  0x82BD 1x1 glyph, data=62266226
0x080  shared 1x1 glyph
total  0xA0
```

`chs_1x2.chunk` 继续沿用 dual-slot pack：

```text
0x000  CHP2 header
0x020  resident slot0, initial chunk1
0x100  resident slot1, initially invalid
0x1E0  source page0
0x2C0  source page1
total  0x3A0
```

## 关键样本

`0x8140` 被故意放进 1x1 与 1x2 两套 map，且使用不同图样，用来验证同字符码跨 mode 不互相污染：

```text
idx 0   0x8140/R2=0x40 -> R0=0x02284B60, data=84488448 84488448
idx 28  0x8140/R2=0x20 -> R0=0x02283040, data=41144114 41144114
idx 114 0x82BD/R2=0x20 -> R0=0x02283060, data=62266226 62266226
```

1x2 双 slot 行为仍保留：

```text
idx 6   0x82DF/R2=0x40 -> R0=0x02284B20, data=C77CC77C C77CC77C
        state=miss=1/82DF/0/0x40, resident_1x1=0, slot0=1, slot1=FFFFFFFF, next=1

idx 18  0x82A2/R2=0x40 -> R0=0x02284C40, data=73377337 73377337
        state=miss=0, resident_1x1=0, slot0=1, slot1=0, next=0

idx 20  0x82C6/R2=0x40 -> R0=0x02284BA0, data=95599559 95599559
        state=miss=0, resident_1x1=0, slot0=1, slot1=0, next=0
```

`state words = miss_flag, miss_char, miss_chunk_id, miss_mode, resident_1x1, slot0, slot1, next_slot`。

## 结论

- dual-mode copy hook 已同时接管 `R2=0x20` 与 `R2=0x40`，并按 mode 选择 `chs_1x1.map/chunk` 或 `chs_1x2.map/chunk`。
- 同一字符码 `0x8140` 在 1x2 命中 `84488448`，在 1x1 命中 `41144114`，证明 1x1/1x2 不再共享错误 glyph 或被单一 `char_code` 表互相污染。
- 1x2 dual-slot 策略在 dual-mode 版本中仍成立：`82DF` miss 后 chunk0 装入 slot1，`82A2` 命中 slot1，`82C6` 仍命中 slot0 的 chunk1。
- 当前 1x1 仍是单 `resident_1x1_chunk_id` 常驻策略；如果后续 1x1 中文 glyph 也需要多 chunk 驻留，需要为 `miss_mode=0x20` 补 page copy 或多 slot consumer。
