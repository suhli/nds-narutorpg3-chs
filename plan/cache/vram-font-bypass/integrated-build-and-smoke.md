# 阶段缓存：动态字体集成构建与冒烟检查

## 背景

用户要求停止继续做单点 probe，改为直接推进可使用方案，后续验证也改为整体验收，只有失败时再用排除法拆分。

本轮把已验证链路收敛为两个集成入口：

```text
tools/build_vram_font_dynamic_cache_rom.py
tools/run_vram_font_integrated_smoke.py
```

## 集成构建入口

构建命令：

```text
.\.venv\Scripts\python.exe -B tools\build_vram_font_dynamic_cache_rom.py
```

默认输出：

```text
rom/narutorpg3_chs_dynamic_font_v0.nds
rom/unpacked/narutorpg3_chs_dynamic_font_v0
```

代码区布局：

```text
0x02073D64  copy hook body, size=0xEC
0x020743E4  consume trampoline, size=0x8
0x020718D8  consume body, size=0xFC
```

默认 font 文件：

```text
data/font/chs_1x1.map    size=0x50
data/font/chs_1x1.chunk  size=0x1A0
data/font/chs_1x2.map    size=0x70
data/font/chs_1x2.chunk  size=0x3A0
```

`--font-dir <dir>` 可替换为外部准备好的 `chs_1x1.map/chunk` 和 `chs_1x2.map/chunk`，不传时使用当前集成样本数据。

ROM 检查：

```text
tools/ndstool.exe -i rom/narutorpg3_chs_dynamic_font_v0.nds
Header CRC OK
Banner CRC OK
```

## 集成冒烟入口

冒烟命令：

```text
.\.venv\Scripts\python.exe -B tools\run_vram_font_integrated_smoke.py --rom rom\narutorpg3_chs_dynamic_font_v0.nds --output plan\cache\vram-font-bypass\integrated-smoke-samples.json
```

一次性检查项：

```text
1x2 shared ok idx=0 r0=0x02284B60
1x2 slot1 ok idx=18 r0=0x02284C40
1x2 slot0 ok idx=20 r0=0x02284BA0
1x1 miss ok idx=28 r0=0x02283040
1x1 resident ok idx=76 r0=0x02283060
final state running
```

关键行为：

```text
0x8140/R2=0x40 -> 1x2 glyph data 84488448
0x8140/R2=0x20 -> first 1x1 miss/fallback data A66AA66A
0x8140/R2=0x20 -> after consumer data 41144114
0x82A2/R2=0x40 -> 1x2 slot1 data 73377337
0x82C6/R2=0x40 -> 1x2 slot0 data 95599559
```

## 当前策略

- 停止新增单点验证 probe。
- 以后默认先构建集成 ROM，再跑一次集成冒烟。
- 冒烟失败后再按失败项拆分排查，例如只拆 1x1 miss、1x2 slot、路径加载或代码区迁移。
- 当前 v0 支持 1x1 两个 source page 与 1x2 两个 source page；继续扩展更多 chunk 时，需要先把 source page 选择升级为通用表或更大的 consumer 代码区。

## 2026-05-28 rebuild_latest

用户要求直接构建。本次先尝试用 `--force` 覆盖默认输出，但旧解包目录中 `rom/unpacked/narutorpg3_chs_dynamic_font_v0/data/a_char/000.n` 在 Windows 下拒绝删除；脚本已加只读文件重试逻辑，但该文件仍无法删除，判断为旧解包目录权限或占用问题。

为避免卡在旧目录清理，本次改用新工作目录和新 ROM 文件名完成构建：

```text
.\.venv\Scripts\python.exe -B tools\build_vram_font_dynamic_cache_rom.py --work rom/unpacked/narutorpg3_chs_dynamic_font_v0_build_latest --output rom/narutorpg3_chs_dynamic_font_v0_build_latest.nds
```

输出：

```text
rom/narutorpg3_chs_dynamic_font_v0_build_latest.nds
rom/unpacked/narutorpg3_chs_dynamic_font_v0_build_latest
```

构建摘要：

```text
copy_hook=0x02073D64 size=0xEC
consume_trampoline=0x020743E4 size=0x8
consume_body=0x020718D8 size=0xFC
chs_1x1.map size=0x50
chs_1x1.chunk size=0x1A0
chs_1x2.map size=0x70
chs_1x2.chunk size=0x3A0
```

`ndstool -i` 检查：

```text
Header CRC OK
Banner CRC OK
```

集成冒烟：

```text
.\.venv\Scripts\python.exe -B tools\run_vram_font_integrated_smoke.py --rom rom\narutorpg3_chs_dynamic_font_v0_build_latest.nds --output plan\cache\vram-font-bypass\integrated-smoke-build-latest-samples.json

1x2 shared ok idx=0 r0=0x02284B60
1x2 slot1 ok idx=18 r0=0x02284C40
1x2 slot0 ok idx=20 r0=0x02284BA0
1x1 miss ok idx=28 r0=0x02283040
1x1 resident ok idx=76 r0=0x02283060
final state running
```

## 2026-05-28 force fallback 构建验证

为避免默认 `--force` 因旧解包目录权限或 ROM 占用直接中断，`tools/build_vram_font_dynamic_cache_rom.py` 已改为：

- 优先删除指定 work/output。
- 删除失败时自动改用同目录下 `_build_<timestamp>` 后缀的新路径。
- 实际输出路径以脚本打印的 `output=` 和 `work=` 为准。

验证命令：

```text
.\.venv\Scripts\python.exe -B tools\build_vram_font_dynamic_cache_rom.py --force
```

本次环境中旧 work 目录仍无法删除，默认 ROM 也被占用，因此脚本自动降级到：

```text
rom/narutorpg3_chs_dynamic_font_v0_build_20260528_231808.nds
rom/unpacked/narutorpg3_chs_dynamic_font_v0_build_20260528_231808
```

构建摘要：

```text
copy_hook=0x02073D64 size=0xEC
consume_trampoline=0x020743E4 size=0x8
consume_body=0x020718D8 size=0xFC
chs_1x1.map size=0x50
chs_1x1.chunk size=0x1A0
chs_1x2.map size=0x70
chs_1x2.chunk size=0x3A0
```

`ndstool -i` 检查：

```text
Header CRC OK
Banner CRC OK
```

集成冒烟：

```text
.\.venv\Scripts\python.exe -B tools\run_vram_font_integrated_smoke.py --rom rom\narutorpg3_chs_dynamic_font_v0_build_20260528_231808.nds --output plan\cache\vram-font-bypass\integrated-smoke-force-fallback-samples.json

1x2 shared ok idx=0 r0=0x02284B60
1x2 slot1 ok idx=18 r0=0x02284C40
1x2 slot0 ok idx=20 r0=0x02284BA0
1x1 miss ok idx=28 r0=0x02283040
1x1 resident ok idx=76 r0=0x02283060
final state running
```

当前结论：集成构建入口已能在旧目录不可删或 ROM 被模拟器占用时继续产出可用 ROM。后续构建后应读取脚本实际打印的 `output=` 路径作为冒烟输入。

## 2026-05-28 font-dir 格式校验

为让 `--font-dir` 更接近可用入口，`tools/build_vram_font_dynamic_cache_rom.py` 已加入当前 v0 字体文件校验：

```text
chs_1x1.map    CHMP, version=1, header=0x20, entry=0x10, glyph_size=0x20
chs_1x1.chunk  CHP1, header=0x20, page_size=0x80, source_pages>=1, resident_slots=1
chs_1x2.map    CHMP, version=1, header=0x20, entry=0x10, glyph_size=0x40
chs_1x2.chunk  CHP2, header=0x20, page_size=0xE0, source_pages>=1, resident_slots=2
```

构建阶段会检查：

```text
map/chunk magic
version/header_size/entry_size/glyph_size/page_size
source_page_count/resident_slots
duplicate char_code
entry.chunk_id < source_page_count
entry.glyph_offset + glyph_size <= page_size
```

验证构建：

```text
.\.venv\Scripts\python.exe -B tools\build_vram_font_dynamic_cache_rom.py --work rom/unpacked/narutorpg3_chs_dynamic_font_v0_validate --output rom/narutorpg3_chs_dynamic_font_v0_validate.nds

1x1_font_format=ok source_pages=2
1x2_font_format=ok source_pages=2
```

外部 `--font-dir` 构建也已验证：

```text
.\.venv\Scripts\python.exe -B tools\build_vram_font_dynamic_cache_rom.py --font-dir rom\unpacked\narutorpg3_chs_dynamic_font_v0_validate\data\font --work rom/unpacked/narutorpg3_chs_dynamic_font_v0_fontdir --output rom/narutorpg3_chs_dynamic_font_v0_fontdir.nds

1x1_font_format=ok source_pages=2
1x2_font_format=ok source_pages=2
Header CRC OK
Banner CRC OK
```

验证产物：

```text
rom/narutorpg3_chs_dynamic_font_v0_validate.nds
rom/unpacked/narutorpg3_chs_dynamic_font_v0_validate
```

`ndstool -i` 检查：

```text
Header CRC OK
Banner CRC OK
```

集成冒烟：

```text
.\.venv\Scripts\python.exe -B tools\run_vram_font_integrated_smoke.py --rom rom\narutorpg3_chs_dynamic_font_v0_validate.nds --output plan\cache\vram-font-bypass\integrated-smoke-validated-format-samples.json

1x2 shared ok idx=0 r0=0x02284B60
1x2 slot1 ok idx=18 r0=0x02284C40
1x2 slot0 ok idx=20 r0=0x02284BA0
1x1 miss ok idx=28 r0=0x02283040
1x1 resident ok idx=76 r0=0x02283060
final state running
```

当前结论：当前集成构建入口已能在构建阶段拒绝不符合 v0 合同的字体文件，避免无效 `--font-dir` 进入模拟器阶段才暴露。
