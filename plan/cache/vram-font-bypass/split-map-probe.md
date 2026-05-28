# 阶段缓存：1x1/1x2 split-map 原型验证

更新时间：2026-05-28

## 目标

把此前临时的单文件结构：

```text
font/chs_probe.bin
```

升级为 1x1 和 1x2 分离的 map/chunk 原型，验证同一个字符码在不同 glyph size 下可以命中不同 glyph 数据，避免只按 `char_code` 查表造成 1x1/1x2 互相污染。

## 新增脚本

```text
tools/patch_vram_font_split_map_probe.py
```

说明：

- `tools/` 被 `.gitignore` 忽略，脚本是本地工程工具产物。
- 该脚本复用 `rom/unpacked/origin/` 作为输入，不修改 `rom/origin.nds`。
- ARM9 hook 仍放在已验证空洞 `0x0207411C` 起，不使用 overlay 尾部追加方案。

## 有效测试 ROM

第一次构建后发现 load hook 的 literal pool 布局不够稳妥，已修正脚本并改用 v2 产物作为有效验证对象：

```text
rom/test_vram_font_split_map_probe_v2.nds
rom/unpacked/vram_font_split_map_probe_v2/
```

构建命令：

```text
.\.venv\Scripts\python.exe -B tools\patch_vram_font_split_map_probe.py --work rom/unpacked/vram_font_split_map_probe_v2 --output rom/test_vram_font_split_map_probe_v2.nds
```

`ndstool -i` 可正常读取 ROM 头：

```text
Game title: NARUTORPG3
Game code: ANTJ
Header CRC: OK
Banner CRC: OK
```

第一次构建的旧解包目录 `rom/unpacked/vram_font_split_map_probe/` 清理时遇到资源文件权限拒绝，暂未继续强删；旧 ROM 和旧采样文件已清理，后续只使用 v2 产物。

## 新增 NitroFS 文件

```text
font/chs_1x1.map    size=0x14
font/chs_1x1.chunk  size=0x40
font/chs_1x2.map    size=0x1C
font/chs_1x2.chunk  size=0xC0
```

当前 map 结构仍保持最小原型：

```text
u32 entry_count
entry[entry_count]:
  u32 char_code
  u32 glyph_offset
```

测试映射：

```text
1x1:
  0x82A2 -> offset 0x00
  0x82BD -> offset 0x20

1x2:
  0x82A2 -> offset 0x00
  0x82CD -> offset 0x40
  0x82DF -> offset 0x80
```

其中 `0x82A2` 故意同时存在于 1x1 和 1x2 map，用于证明运行时会按 `R2` 分流到不同 chunk。

## Patch 布局

```text
020869E0 -> B  02074200
0208914C -> BL 0207411C
02089190 -> BL 02074140

0207411C  save-current-char hook
02074140  split-map lookup hook
02074200  font init tail hook, calls 0207F80C four times

02074340  "font/chs_1x1.map"
02074354  "font/chs_1x1.chunk"
02074368  "font/chs_1x2.map"
0207437C  "font/chs_1x2.chunk"

020743A0  chs_1x1_map_ptr
020743A4  chs_1x1_map_size
020743A8  chs_1x1_chunk_ptr
020743AC  chs_1x1_chunk_size
020743B0  chs_1x2_map_ptr
020743B4  chs_1x2_map_size
020743B8  chs_1x2_chunk_ptr
020743BC  chs_1x2_chunk_size
020743C0  current_char
```

copy hook 分流规则：

```text
R2 == 0x20 -> lookup chs_1x1.map, base chs_1x1.chunk
R2 == 0x40 -> lookup chs_1x2.map, base chs_1x2.chunk
other      -> keep original R0
```

任一 map/chunk 指针为 0 时，hook 保留原 `R0` 并尾调用 `020087BC`。

## MCP 验证

采样命令：

```text
.\.venv\Scripts\python.exe -B tools\sample_vram_font_chars_mcp.py --rom rom\test_vram_font_split_map_probe_v2.nds --current-char-address 020743C0 --max-samples 180 --seconds 24 --output plan\cache\vram-font-bypass\split-map-v2-samples.json
```

运行时加载指针区：

```text
020743A0:
02282F80 00000014 02282FC0 00000040
02283020 0000001C 02283060 000000C0
00008140
```

含义：

```text
1x1 map   -> 0x02282F80 size 0x14
1x1 chunk -> 0x02282FC0 size 0x40
1x2 map   -> 0x02283020 size 0x1C
1x2 chunk -> 0x02283060 size 0xC0
```

chunk 数据确认：

```text
1x1 chunk @ 02282FC0:
15151515 51515151 ... 26262626 62626262 ...

1x2 chunk @ 02283060:
37373737 73737373 ... 48484848 84848484 ... 59595959 95959595 ...
```

关键采样：

```text
0x82CD, R2=0x40 -> R0=0x022830A0  (1x2 chunk + 0x40)
0x82DF, R2=0x40 -> R0=0x022830E0  (1x2 chunk + 0x80)
0x82A2, R2=0x40 -> R0=0x02283060  (1x2 chunk + 0x00)

0x82BD, R2=0x20 -> R0=0x02282FE0  (1x1 chunk + 0x20)
0x82A2, R2=0x20 -> R0=0x02282FC0  (1x1 chunk + 0x00)
```

收尾状态：

```text
running=1 ARM9_PC=0x01FFBCEC ARM7_PC=0x038042B0
```

## 结论

已验证：

- 1x1/1x2 可以拆成两套独立 map/chunk 文件。
- 字体初始化阶段可以连续调用 `0207F80C` 加载四个 NitroFS 文件到普通 RAM。
- copy hook 可以用 `R2` 区分 1x1 和 1x2。
- 同一个字符码 `0x82A2` 在 `R2=0x40` 和 `R2=0x20` 下分别命中不同 chunk，不再互相污染。
- map/chunk 分离比单文件 `chs_probe.bin` 更接近后续正式格式，也方便后续把 glyph 数据改成分页或分块加载。

## 下一步

- 将 split-map 原型提升为正式格式草案，补 magic/version/header/entry flags。
- 设计 glyph chunk 的分页或分块加载策略，不要把完整中文字模作为一个大文件常驻 RAM。
- 继续保留 `R2` 分流作为早期实现路线；后续如需宽度或排版控制，再评估是否迁移到 `0208671C` 层处理。
