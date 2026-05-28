# 阶段缓存：dual-mode 1x1 page copy 原型

## 背景

上一轮 `chunk-table-dual-mode-probe` 已证明 1x1/1x2 可以在同一个 copy hook 中按 `R2=0x20/0x40` 分流，且同一字符码不会互相污染。剩余风险是 1x1 仍只验证了 resident chunk 常驻，没有让 `miss_mode=0x20` 进入真实 page copy。

本轮新增 1x1 page-copy consumer 原型，验证 1x1 miss 也能在 copy hook 外消费并换入目标 page。

## 新增产物

```text
tools/patch_vram_font_chunk_table_dual_mode_1x1_copy_probe.py
rom/test_vram_font_chunk_table_dual_mode_1x1_copy_probe.nds
plan/cache/vram-font-bypass/chunk-table-dual-mode-1x1-copy-samples.json
plan/cache/vram-font-bypass/chunk-table-dual-mode-1x1-copy-long-samples.json
```

ROM 校验：

```text
tools/ndstool.exe -i rom/test_vram_font_chunk_table_dual_mode_1x1_copy_probe.nds
Header CRC OK
Banner CRC OK
```

## 代码区布局

`0x020743E4` 后面的主扩展空洞已经被 dual-slot consumer 占满，因此本轮把 consumer 拆成 trampoline + 远端 body：

```text
0x02074140  copy trampoline, size=0x4
0x02073D64  copy hook body, size=0xEC
0x020743E4  consume trampoline, size=0x8
0x020718D8  consume body, size=0xFC
0x0207411C  extended payload, size=0x380
```

没有使用此前验证会被运行时数据污染的 `0x0207A668` 附近空洞。

## 1x1 pack

本轮把 `chs_1x1.chunk` 临时改成单 resident slot + 两个源 page：

```text
0x000  CHP1 header
0x020  resident 1x1 page, initial chunk0
0x0A0  source page0
0x120  source page1
total  0x1A0
```

1x1 consumer 使用 `source_page0 + (miss_chunk_id << 7)` 选择 source page；当前 v0 支持 `chunk_id=0/1` 两页。后续如果 1x1 chunk 数超过 2，需要迁移到更大的代码区或把 page copy 抽成可复用例程。

## 关键样本

1x2 路径仍保持 dual-slot 行为：

```text
idx 0   0x8140/R2=0x40 -> R0=0x02284B60, data=84488448 84488448
idx 6   0x82DF/R2=0x40 -> R0=0x02284B20, data=C77CC77C C77CC77C, miss=1/82DF/0/0x40
idx 18  0x82A2/R2=0x40 -> R0=0x02284C40, data=73377337 73377337, slot0=1, slot1=0
idx 20  0x82C6/R2=0x40 -> R0=0x02284BA0, data=95599559 95599559, slot0=1, slot1=0
```

1x1 首次 miss 与 consumer 后命中：

```text
idx 28  0x8140/R2=0x20 -> R0=0x02283040, data=A66AA66A A66AA66A
        state=miss=1/8140/1/0x20, resident_1x1=0

idx 76  0x8140/R2=0x20 -> R0=0x02283060, data=41144114 41144114
        state=miss=0/8140/1/0x20, resident_1x1=1
```

`state words = miss_flag, miss_char, miss_chunk_id, miss_mode, resident_1x1, slot0, slot1, next_slot`。

## 结论

- `miss_mode=0x20` 已能在 `0x0208913C` consumer 层触发真实 1x1 page copy。
- 1x1 首次未驻留时先返回 resident page 内 fallback glyph；consumer 后续把 chunk1 拷入 resident page，再次绘制同字符时命中目标 glyph。
- 1x2 dual-slot 换页与 slot 保留行为在这个版本中仍成立。
- 当前 1x1 page copy 已支持 `chunk_id=0/1`；正式版若要扩展到更多 page，需要把 `chunk_id -> source page` 选择从两页逻辑升级为通用表或乘法/循环逻辑。
