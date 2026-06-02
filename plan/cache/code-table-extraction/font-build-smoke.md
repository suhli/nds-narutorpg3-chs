# 阶段缓存：font-dir 构建冒烟

更新时间：2026-06-02

## 命令

```text
.\.venv\Scripts\python.exe -B tools\build_vram_font_files.py --manifest text\code_table\font_manifest.json --output-dir plan\cache\code-table-extraction\font-build-smoke
```

## 输出摘要

```text
output_dir=plan\cache\code-table-extraction\font-build-smoke
entries=1986
1x1_source_pages=993
1x2_source_pages=993
chs_1x1.map size=0x7C40
chs_1x1.chunk size=0x1F120
chs_1x2.map size=0x7C40
chs_1x2.chunk size=0x366C0
```

## 静态格式核对

```text
chs_1x1.map: magic=CHMP size=0x7C40
chs_1x1.chunk: magic=CHP1 size=0x1F120
chs_1x2.map: magic=CHMP size=0x7C40
chs_1x2.chunk: magic=CHP2 size=0x366C0
```

产物：

```text
plan/cache/code-table-extraction/font-build-smoke/chs_1x1.map
plan/cache/code-table-extraction/font-build-smoke/chs_1x1.chunk
plan/cache/code-table-extraction/font-build-smoke/chs_1x2.map
plan/cache/code-table-extraction/font-build-smoke/chs_1x2.chunk
plan/cache/code-table-extraction/font-build-smoke/manifest.resolved.json
```

本阶段没有调用 ROM 集成脚本，没有重新打包 ROM。
