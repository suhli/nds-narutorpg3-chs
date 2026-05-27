# 阶段缓存：动态 glyph 缓存正式设计

更新时间：2026-05-27

## 当前结论

当前最可行路线是方案 A：动态 glyph 缓存。

已确认的基础能力：

- `0208913C -> 0208916C -> 0208671C -> 02089170 -> 02089190` 是实际绘制链路。
- `0208914C` 可以保存当前字符码。
- `02089190` 前可以按字符码替换 `R0=glyph_source`。
- 原复制函数 `020087BC` 可以从 ARM9 RAM 读取 glyph 数据，不要求源地址必须是原 VRAM 字库区。
- overlay 尾部追加 hook 会踩 overlay_0000 BSS，不能再使用；当前 ARM9 空洞 hook 可用。

## 目标

把“单字符测试替换”扩展为可服务中文显示的最小动态缓存：

```text
text char code -> lookup custom glyph -> prepare glyph bytes -> R0 points to prepared glyph -> 020087BC copies to render buffer
```

该阶段只做机制设计和最小原型，不进入大规模文本 dump 和翻译。

## 设计草案

### 1. 字符识别

短期仍沿用 `0208914C` 保存当前字符码：

```text
CURRENT_CHAR_ADDR = 0x020741C0
```

正式实现时可以继续在 `02089190` 前读取该值，也可以迁移到 `0208671C` 处统一处理字符码到 glyph 的映射。

### 2. glyph 数据来源

候选优先级：

1. NitroFS 新增文件，例如 `data/font/chs_1x2.chr` 和 `data/font/chs_map.bin`。
2. ARM9 扩展区或明确空洞，只用于小型测试，不适合作为最终全量中文 glyph 仓库。
3. 独立 overlay，适合放代码，不适合直接放大量字模数据。

推荐先用 NitroFS 新文件做正式数据来源，因为它不挤占 VRAM，也不会扩大 overlay BSS 风险。

### 3. 映射结构

最小映射项：

```text
u16 char_code
u16 flags_or_width
u32 glyph_offset
```

其中 `glyph_offset` 指向中文 glyph 文件内偏移。1x1 和 1x2 可以先拆成两个 map，避免早期把 mode 逻辑混在一起。

### 4. 缓存槽

初版可以先做“单槽 RAM glyph 缓存”：

```text
CUSTOM_GLYPH_ADDR = 0x02074180
```

命中中文字符时，把 glyph 读入或复制到该地址，再把 `R0` 改成 `CUSTOM_GLYPH_ADDR`。

单槽方案适合验证，但正式显示同屏多字时需要扩展为多槽：

```text
slot {
  u16 char_code
  u16 mode
  u32 glyph_addr
  u32 last_used
}
```

### 5. 关键风险

- `02074180` 目前只是测试地址，容量很小，不能承载多槽缓存。
- 需要确认能否在绘制路径中同步读取 NitroFS；如果不能，需要提前把中文 glyph 文件加载到普通 RAM。
- 需要确认 1x1 字体路径是否复用同一 copy 逻辑。
- 需要确认字宽、换行和菜单布局是否只依赖 `.tbl`，还是另有宽度表。

## 下一步实验

1. 构建一个“两个字符映射到两个 RAM glyph”的测试 ROM。
2. 将 `match-char` 从单值扩展为小表查找，例如 `0x82CD`、`0x82DF`。
3. 先不接 NitroFS 文件读取，只把两个 glyph 放在 ARM9 空洞，证明多字符选择逻辑。
4. 通过 DeSmuME MCP 验证两个不同字符都能在 `020087BC` 前把 `R0` 替换到不同 glyph 地址。

## 2026-05-27 多字符 probe 进展

已新增：

```text
tools/patch_vram_font_multi_char_hook_probe.py
rom/test_vram_font_multi_char_hook_probe.nds
rom/test_vram_font_multi_char_8140_probe.nds
```

默认 `0x82CD/0x82DF` 版本已完成构建和静态检查；本轮输入路径未稳定触发这两个字符。

运行时已验证 `0x8140 -> 0x020741A0`：

```text
020087BC:
current_char=00008140
R0=0x020741A0
R1=0x02292A40
```

结论：两项小表 hook 的第一项分流机制成立。下一步需要找到第二个可稳定触发的字符路径，或者把小表改为运行中已知连续出现的两个字符继续验证第二项。
