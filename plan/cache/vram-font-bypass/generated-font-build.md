# 阶段缓存：真实字体文件生成器

## 背景

集成 ROM 构建入口已经支持 `--font-dir`，本轮继续补“真实字体文件生成器”，把 TTF 渲染结果打包成当前 v0 动态字体系统需要的四个文件：

```text
chs_1x1.map
chs_1x1.chunk
chs_1x2.map
chs_1x2.chunk
```

## 新增入口

```text
tools/build_vram_font_files.py
```

输入支持：

```text
--manifest <json-or-text>
--chars <string> --start-code <code>
--font-1x1 <ttf>
--font-1x2 <ttf>
--output-dir <dir>
```

默认字体：

```text
assets/fusion-pixel-8px-monospaced-zh_hans.ttf
assets/FashionBitmap16_0.092.ttf
```

依赖已安装到当前 `.venv`：

```text
uv pip install freetype-py pillow
```

其中当前生成器实际依赖 `freetype-py`；`pillow` 是既有 assets 字体预览脚本依赖。

## 生成格式

`1x1`：

```text
CHMP map, glyph_size=0x20
CHP1 chunk pack, page_size=0x80, resident_slots=1
每页 offset 0x20 为 fallback glyph，offset 0x40/0x60 为两个自定义 glyph 槽
```

`1x2`：

```text
CHMP map, glyph_size=0x40
CHP2 chunk pack, page_size=0xE0, resident_slots=2
每页 offset 0x20 为 fallback glyph，offset 0x60/0xA0 为两个自定义 glyph 槽
```

当前 packer 至少生成 2 个 source page，以匹配 v0 初始化状态：

```text
resident_1x1_chunk_id = 0
resident_1x2_slot0_chunk_id = 1
resident_1x2_slot1_chunk_id = INVALID
```

## 1x2 source page 泛化

`tools/patch_vram_font_chunk_table_dual_mode_1x1_copy_probe.py` 的 1x2 consumer 已从：

```text
chunk_id == 0 -> source page 0
chunk_id != 0 -> source page 1
```

改为按：

```text
source_page = source_base + chunk_id * 0xE0
```

计算 source page 地址。当前已完成回归冒烟；超过 2 页的真实运行命中仍需要在后续文本或专门集成样本里覆盖。

## 本轮生成样本

manifest：

```text
plan/cache/vram-font-bypass/generated-font-smoke-manifest.txt
```

内容按集成冒烟路径排序：

```text
0x82A2 新
0x82DF 游
0x8140 戏
0x82C6 字
```

生成命令：

```text
.\.venv\Scripts\python.exe -B tools\build_vram_font_files.py --manifest plan\cache\vram-font-bypass\generated-font-smoke-manifest.txt --output-dir plan\cache\vram-font-bypass\generated-font-smoke
```

输出：

```text
output_dir=plan\cache\vram-font-bypass\generated-font-smoke
entries=4
1x1_source_pages=2
1x2_source_pages=2
chs_1x1.map size=0x60
chs_1x1.chunk size=0x1A0
chs_1x2.map size=0x60
chs_1x2.chunk size=0x3A0
```

## 集成构建

构建命令：

```text
.\.venv\Scripts\python.exe -B tools\build_vram_font_dynamic_cache_rom.py --font-dir plan\cache\vram-font-bypass\generated-font-smoke --work rom/unpacked/narutorpg3_chs_dynamic_font_v0_generated_font --output rom/narutorpg3_chs_dynamic_font_v0_generated_font.nds
```

输出：

```text
rom/narutorpg3_chs_dynamic_font_v0_generated_font.nds
rom/unpacked/narutorpg3_chs_dynamic_font_v0_generated_font
```

构建摘要：

```text
1x1_font_format=ok source_pages=2
1x2_font_format=ok source_pages=2
copy_hook=0x02073D64 size=0xEC
consume_trampoline=0x020743E4 size=0x8
consume_body=0x020718D8 size=0xFC
```

`ndstool -i`：

```text
Header CRC OK
Banner CRC OK
```

## 集成冒烟

`tools/run_vram_font_integrated_smoke.py` 已新增：

```text
--font-dir <dir>
```

传入后会从生成的 `chs_1x1/chs_1x2` 文件读取期望 glyph 前 8 字节，不再依赖旧 probe 的硬编码花纹。

冒烟命令：

```text
.\.venv\Scripts\python.exe -B tools\run_vram_font_integrated_smoke.py --rom rom\narutorpg3_chs_dynamic_font_v0_generated_font.nds --font-dir plan\cache\vram-font-bypass\generated-font-smoke --output plan\cache\vram-font-bypass\integrated-smoke-generated-font-samples.json
```

结果：

```text
1x2 shared ok idx=0 r0=0x02284B60
1x2 slot1 ok idx=18 r0=0x02284C40
1x2 slot0 ok idx=20 r0=0x02284BA0
1x1 miss ok idx=28 r0=0x02283040
1x1 resident ok idx=76 r0=0x02283060
final state running
```

## 回归冒烟

为确认 `--font-dir` 期望值读取没有破坏旧 probe 花纹路径，保留默认期望值再跑一次：

```text
.\.venv\Scripts\python.exe -B tools\run_vram_font_integrated_smoke.py --rom rom\narutorpg3_chs_dynamic_font_v0_validate.nds --output plan\cache\vram-font-bypass\integrated-smoke-regression-after-fontgen-samples.json
```

结果：

```text
1x2 shared ok idx=0 r0=0x02284B60
1x2 slot1 ok idx=18 r0=0x02284C40
1x2 slot0 ok idx=20 r0=0x02284BA0
1x1 miss ok idx=28 r0=0x02283040
1x1 resident ok idx=76 r0=0x02283060
final state running
```

## 当前结论

- 当前 v0 已具备“TTF -> font-dir -> ROM -> 模拟器整体验收”的闭环。
- 真实中文字模生成不再需要手写 probe 花纹。
- 下一步可以接文本编码/字符分配表，让 `manifest` 从汉化文本字符集或手动编码表生成。
