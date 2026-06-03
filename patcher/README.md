# Naruto RPG3 汉化补丁打包器

这个目录是当前全量文本回写和菜单回写基线的冻结打包包。

## 默认构建

```powershell
.\.venv\Scripts\python.exe patcher\patcher.py --output rom\narutorpg3_chs_patcher.nds
```

默认构建会使用：

- `patcher/resources/text/encoded-preview-struct-adjusted.tsv`
- `patcher/resources/text/zh_code_table.tsv`
- `patcher/resources/text/font_manifest.json`
- `patcher/resources/menu/overlay_menu_translations.tsv`
- `patcher/resources/fonts/1x1.ttf` 和 `patcher/resources/fonts/1x2.ttf`
- `patcher/tools/` 下内置的构建脚本和 `ndstool.exe`

构建时会在需要时把 `rom/origin.nds` 解包到 `patcher/work/origin_unpacked`，然后生成字体 payload、写回文本和菜单、修改字体 hook、重打包新 ROM，并对输出 ROM 执行 `ndstool -i` 校验。

如果指定的输出 ROM 已存在，patcher 会写入带时间戳的同名旁路文件，不会覆盖旧 ROM。

## 替换字体

默认 `1x2.ttf` 当前使用 `fusion-pixel-12px-monospaced-zh_hans.ttf` 的字形。1x2 字模生成时不再把 16 像素宽字形压缩到 8 像素宽，而是按 8x12 目标格渲染后垂直居中放入 8x16 双 tile。

同一个 TTF 同时用于 1x1 和 1x2 字体：

```powershell
.\.venv\Scripts\python.exe patcher\patcher.py --font path\to\font.ttf --output rom\narutorpg3_chs_font_test.nds
```

分别指定 1x1 和 1x2 字体：

```powershell
.\.venv\Scripts\python.exe patcher\patcher.py --font-1x1 path\to\8px.ttf --font-1x2 path\to\16px.ttf --output rom\narutorpg3_chs_font_test.nds
```

## 替换译文

使用替换后的冻结译文 TSV，一次性重新生成码表、字体 manifest、编码预览、结构审计结果、菜单翻译、字体 payload 和 ROM：

```powershell
.\.venv\Scripts\python.exe patcher\patcher.py --translation-table path\to\frozen_translation.tsv --output rom\narutorpg3_chs_text_test.nds
```

如果直接修改了内置的 `patcher/resources/text/frozen_translation.tsv`：

```powershell
.\.venv\Scripts\python.exe patcher\patcher.py --rebuild-text-assets --output rom\narutorpg3_chs_text_test.nds
```

## 使用编码预览构建

如果已经准备好调整后的编码预览 TSV：

```powershell
.\.venv\Scripts\python.exe patcher\patcher.py --translation-preview path\to\encoded_preview.tsv --output rom\narutorpg3_chs_preview_test.nds
```

## 构建产物

每次运行都会创建一个 `patcher/work/build_*` 目录，里面包含：

- `patcher.log`：本次构建命令和校验输出。
- `text_assets/`：本次生成或审计后的文本素材。
- `font_build/`：本次生成的字体 payload。
- `rom_work/`：本次 ROM 解包和修改工作目录。
- `patcher-build-summary.json`：本次构建摘要。
- `missing-chars-report.json`：缺字汇总报告。
- `missing-chars.tsv`：按来源列出的缺字总表；字体缺字会同时列出 `mode`、`code` 和实际缺字的 TTF 路径。
- `font-missing-chars.tsv`：按字体模式列出的 TTF 缺字清单，同样包含实际 TTF 路径。

## 缺字处理

构建遇到缺字不会直接失败。

- 文本编码缺字：记录到缺字报告，并跳过对应文本写回行，让原始内容保留在 ROM 中。
- 菜单编码缺字：记录到缺字报告，对应菜单行不会写回。
- TTF 字形缺失：记录到缺字报告，标明是 1x1 还是 1x2 字体以及对应 TTF 路径，字体 payload 仍继续生成。

构建结束时，终端会打印总缺字数、文本缺字数、菜单缺字数和字体缺字数。字体缺字会继续拆成 `missing_chars_font_1x1_*`、`missing_chars_font_1x2_*`，并打印对应的 TTF 路径。

## 失败条件

替换译文重建时，以下情况会直接中止构建：

- 结构审计失败。
- 控制符不匹配。
- 固定槽容量溢出。
- 菜单翻译存在非 ready 且不是缺字导致的行。

## 安全规则

- `rom/origin.nds` 只作为输入读取。
- 不覆盖、原地 patch 或把 `rom/origin.nds` 作为输出。
- 输出 ROM 始终写到新的路径；如果目标路径已存在，会自动改用带时间戳的新文件名。
