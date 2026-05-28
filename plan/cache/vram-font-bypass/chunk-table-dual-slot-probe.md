# Chunk table 双 slot 原型验证

日期：2026-05-28

## 背景

`chunk-table-resident-copy-probe` 已证明 `0x0208913C` consumer 可以把目标 1x2 page 拷入 heap 内 resident page。该版本的限制是只有一个 1x2 resident slot：切到 chunk0 后，chunk1 字符会再次 miss。

本次验证最小双 slot 策略：slot0 初始保留 chunk1，slot1 初始无效；首次遇到 chunk0 miss 时，把 chunk0 装入 slot1，不覆盖 slot0。

## 新增文件

```text
tools/patch_vram_font_chunk_table_dual_slot_probe.py
rom/test_vram_font_chunk_table_dual_slot_v2_probe.nds
plan/cache/vram-font-bypass/chunk-table-dual-slot-v2-samples.json
```

中间构建还产生了：

```text
rom/test_vram_font_chunk_table_dual_slot_probe.nds
plan/cache/vram-font-bypass/chunk-table-dual-slot-samples.json
```

该中间版本已证明 slot1 装入 chunk0，但原文本流没有再次出现 chunk1 测试字符；v2 加入 `0x82C6 -> chunk1` 的 repeat-char map 项，用于验证 slot0 是否仍有效。

## Hook 布局

copy hook 主体已经放不进 `0x02074140..0x02074220` 的 `0xE0` 预算，因此本次改为：

```text
0x02074140  copy trampoline, size=0x4
0x02073D64  copy hook body, size=0xCC
0x020743E4  consume hook, size=0xB8
0x0207411C  extended payload, size=0x380
```

变量区扩展：

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

当前 dual-slot probe 的 copy hook 只接管 `R2=0x40` 的 1x2 路径；`R2=0x20` 暂时回到原始 VRAM copy，用于把尺寸风险集中在 1x2 缓存策略上。

## 文件布局

`chs_1x2.chunk` v2：

```text
0x000  CHP2 header
0x020  resident slot0, initial page1
0x100  resident slot1, initially empty
0x1E0  source page0
0x2C0  source page1
total  0x3A0
```

初始 slot 状态：

```text
slot0 = 1
slot1 = 0xFFFFFFFF
next_slot = 1
```

`0x82C6` 被额外加入 map，指向 chunk1 的 `0xA0` glyph offset，用来在 chunk0 装入 slot1 后验证 slot0 仍能命中 chunk1。

## 验证

ROM 检查：

```text
rom/test_vram_font_chunk_table_dual_slot_v2_probe.nds
title=NARUTORPG3
code=ANTJ
Header CRC OK
Banner CRC OK
```

采样命令：

```text
.\.venv\Scripts\python.exe -B tools\sample_vram_font_chars_mcp.py --rom rom\test_vram_font_chunk_table_dual_slot_v2_probe.nds --current-char-address 020743C0 --extra-read state=020743C4:32,ptrs=020743A0:32 --read-r0-size 8 --stop-after-chars 0x82CD,0x82DF,0x82A2,0x82C6 --max-samples 80 --seconds 30 --output plan\cache\vram-font-bypass\chunk-table-dual-slot-v2-samples.json
```

运行时指针：

```text
1x2_map_ptr   = 0x02283080 size=0x60
1x2_chunk_ptr = 0x02283100 size=0x3A0
slot0 page    = 0x02283120
slot1 page    = 0x02283200
```

关键样本：

```text
idx 4   0x82CD/R2=0x40 -> R0=0x022831C0, data=95599559 95599559
        state=miss0, slot0=1, slot1=FFFFFFFF, next=1

idx 6   0x82DF/R2=0x40 -> R0=0x02283140, data=C77CC77C C77CC77C
        state=miss=1/82DF/0/0x40, slot0=1, slot1=FFFFFFFF, next=1

idx 18  0x82A2/R2=0x40 -> R0=0x02283260, data=73377337 73377337
        state=miss0, slot0=1, slot1=0, next=0

idx 20  0x82C6/R2=0x40 -> R0=0x022831C0, data=95599559 95599559
        state=miss0, slot0=1, slot1=0, next=0
```

字段解释：

```text
state words = miss_flag, miss_char, miss_chunk_id, miss_mode, resident_1x1, slot0, slot1, next_slot
```

判断：

- 双 slot 策略成立：`82DF` 首次 miss 后，consumer 把 chunk0 装入 slot1，并保留 slot0 的 chunk1。
- `82A2/chunk0` 后续命中 slot1 的 page0 图样 `73377337`。
- `82C6/chunk1` 随后仍命中 slot0 的 page1 图样 `95599559`，没有触发新的 miss。
- 这解决了上一版单 slot 在 chunk0/chunk1 间来回失效的问题。

## 限制

- 当前只是 1x2 双 slot 原型，1x1 路径未纳入 dual copy hook。
- `next_slot` 是简单轮换策略；正式方案需要在更多 chunk 下设计替换策略，或在文本块入口预扫本轮所需 chunk。
- copy hook 主体已迁到 `0x02073D64`，`0x020743E4` consumer 刚好占满剩余扩展空洞；后续继续增长需要重新规划代码区，而不是继续硬塞当前空洞。
