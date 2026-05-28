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

## 9. 1x1 路径结论

已验证 1x1 字体也走同一个复制入口：

```text
02089190 -> 020087BC
```

关键样本：

```text
baseline:
current_char=0x8140 R0=0x06880000 R2=0x20

RAM glyph:
current_char=0x82BD R0=0x02282FA0 R2=0x20
current_char=0x82A2 R0=0x02282F60 R2=0x20
```

结论：

```text
1x1 可以用同一个 copy hook 替换 R0。
正式 map 需要区分 1x1/1x2，不能只按 char_code 查找。
```

## 10. split-map 验证结论

已验证：

```text
font/chs_1x1.map
font/chs_1x1.chunk
font/chs_1x2.map
font/chs_1x2.chunk
```

可以在字体初始化阶段加载到普通 RAM，并由 `02089190` copy hook 按 `R2` 选择对应 map/chunk：

```text
R2=0x20 -> 1x1 map/chunk
R2=0x40 -> 1x2 map/chunk
```

关键样本：

```text
0x82A2, R2=0x40 -> R0=0x02283060
0x82A2, R2=0x20 -> R0=0x02282FC0
```

这证明同一字符码可以在 1x1/1x2 中命中不同 glyph，不会再被单一 `char_code -> glyph_offset` 表污染。

当前判断：

```text
split-map 是动态 glyph 缓存正式格式的早期主线。
下一步应补正式 header/magic/version，并继续设计 glyph chunk 分页或分块加载。
```

## 11. formal v0 格式验证结论

已验证带 header 的正式格式：

```text
map   "CHMP", header_size=0x20, entry_size=0x10
chunk "CHCK", header_size=0x20, compression=0
```

运行时加载：

```text
1x1 map   -> 0x02282F80 size 0x40
1x1 chunk -> 0x02282FE0 size 0x60
1x2 map   -> 0x02283060 size 0x50
1x2 chunk -> 0x022830E0 size 0xE0
```

关键样本：

```text
0x82A2, R2=0x40 -> R0=0x02283100
0x82A2, R2=0x20 -> R0=0x02283000
```

这证明正式 header 不破坏当前 `02089190` copy hook 路线。当前 `glyph_offset` 从 chunk 文件起点计算，因此第一枚 glyph 的 offset 是 `0x20`。

当前判断：

```text
formal v0 可作为动态字体文件基础。
下一步应设计 chunk_id、chunk table、缺字 fallback 和查找性能优化。
```

## 12. chunk_id fallback 验证结论

已验证 formal v0 entry 的 `chunk_id` 字段可以进入运行时决策。

新增 ROM：

```text
rom/test_vram_font_chunk_fallback_probe.nds
```

当前 hook 规则：

```text
chunk_id == 0 -> chunk_base + glyph_offset
chunk_id != 0 -> chunk_base + 0x20
```

关键样本：

```text
0x82CD, R2=0x40 -> R0=0x02283120  fallback
0x82BD, R2=0x20 -> R0=0x02283000  fallback
0x82A2, R2=0x40 -> R0=0x02283160  resident
0x82A2, R2=0x20 -> R0=0x02283020  resident
0x82DF, R2=0x40 -> R0=0x022831A0  resident
```

这说明缺页或未驻留 chunk 的临时行为可以由自定义 fallback glyph 接管，不必落回原 VRAM 日文字形。后续需要把 fallback 前的路径补成真实 chunk table 和按页加载。

## 13. resident-slot 验证结论

已验证 1x2 路径可以用 resident slot 判断 `chunk_id` 是否驻留。

新增 ROM：

```text
rom/test_vram_font_chunk_table_probe.nds
```

关键样本：

```text
resident_1x2_chunk_id=1
0x82CD, R2=0x40 -> R0=0x022831A0  resident hit
0x82DF, R2=0x40 -> R0=0x02283120  fallback
```

新的约束也已经明确：

```text
copy_hook_size=0xC0
0x02074140..0x02074200 已用满
```

因此后续不能继续把复杂分页逻辑直接追加到当前 copy hook 中。1x1 resident-slot 正例仍需补采样验证。

## 14. 1x1 resident-slot 补充验证结论

新增 ROM：

```text
rom/test_vram_font_chunk_table_1x1_probe.nds
```

构建参数：

```text
--char-1x1-extra-chunk-id 0
```

关键样本：

```text
0x82BD, R2=0x20 -> R0=0x02283040  resident hit
```

至此，单 resident slot 的基本分支已经覆盖：

```text
1x2 resident hit: 0x82CD -> 0x022831A0
1x2 fallback:    0x82DF -> 0x02283120
1x1 resident hit: 0x82BD -> 0x02283040
```

下一步重点不应是继续往当前 copy hook 追加逻辑，而是解决 hook 空间、查找效率和缺页调度位置。

## 15. hook 瘦身与同空洞迁移验证结论

新增 ROM：

```text
rom/test_vram_font_chunk_table_slim_moved_probe.nds
```

该版本将 copy hook 的变量读取压缩为单一 `vars_base` literal，并把 load hook 从 `0x02074200` 后移到 `0x02074220`。

静态结果：

```text
copy_hook_size=0xA0
copy_budget=0xE0
copy_margin=0x40
load_hook_addr=0x02074220
```

关键样本：

```text
0x82CD, R2=0x40 -> R0=0x022831A0
0x82DF, R2=0x40 -> R0=0x02283120
0x82BD, R2=0x20 -> R0=0x02283040
```

这证明 hook 瘦身与主空洞内部代码重排不会破坏 resident/fallback 决策。当前可用余量只有 `0x40`，适合继续验证极小状态逻辑；真实缺页加载和复杂查找仍应放到逐字 copy hook 之外。

## 16. chunk miss flag 验证结论

新增 ROM：

```text
rom/test_vram_font_chunk_table_miss_flag_probe.nds
```

该版本在 resident slot 不匹配时继续返回 fallback glyph，并把 miss 信息写到：

```text
0x020743C4  miss_flag
0x020743C8  miss_char
0x020743CC  miss_chunk_id
0x020743D0  miss_mode
```

关键样本：

```text
0x82DF, R2=0x40 -> R0=0x02283120, miss=00000001 000082DF 00000000 00000040
0x82A2, R2=0x40 -> R0=0x02283120, miss=00000001 000082A2 00000000 00000040
0x82CD, R2=0x40 -> R0=0x022831A0, miss_flag=0
0x82BD, R2=0x20 -> R0=0x02283040, miss_flag=0
```

结论：copy hook 能稳定产出最小 miss 状态，且不破坏 resident/fallback R0。当前 hook size 为 `0xC0`，仍在后移 load hook 后的 `0xE0` 预算内；后续重点应转向 miss 消费点和 chunk 加载调度。
