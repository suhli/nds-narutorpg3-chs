# Naruto RPG3 CHS Patcher

This directory is the frozen patching bundle for the current full writeback build.

## Default Build

```powershell
.\.venv\Scripts\python.exe patcher\patcher.py --output rom\narutorpg3_chs_patcher.nds
```

The default build uses:

- `patcher/resources/text/encoded-preview-struct-adjusted.tsv`
- `patcher/resources/text/zh_code_table.tsv`
- `patcher/resources/text/font_manifest.json`
- `patcher/resources/menu/overlay_menu_translations.tsv`
- the bundled default TTF files under `patcher/resources/fonts/`

It unpacks `rom/origin.nds` to `patcher/work/origin_unpacked` when needed, generates font payloads, patches text/menu/font payloads, repacks a new ROM, then runs `ndstool -i` on the output.

If the requested output ROM already exists, the patcher writes to a timestamped sibling path instead of overwriting it.

## Replace Font

Use one TTF for both font modes:

```powershell
.\.venv\Scripts\python.exe patcher\patcher.py --font path\to\font.ttf --output rom\narutorpg3_chs_font_test.nds
```

Or provide separate TTF files:

```powershell
.\.venv\Scripts\python.exe patcher\patcher.py --font-1x1 path\to\8px.ttf --font-1x2 path\to\16px.ttf --output rom\narutorpg3_chs_font_test.nds
```

## Replace Translation

Use a replacement frozen translation TSV and rebuild code table, font manifest, encoded preview, structure audit output, menu translations, font payloads, and ROM in one run:

```powershell
.\.venv\Scripts\python.exe patcher\patcher.py --translation-table path\to\frozen_translation.tsv --output rom\narutorpg3_chs_text_test.nds
```

If you edit the bundled `patcher/resources/text/frozen_translation.tsv` directly:

```powershell
.\.venv\Scripts\python.exe patcher\patcher.py --rebuild-text-assets --output rom\narutorpg3_chs_text_test.nds
```

## Direct Preview Build

If an adjusted encoded preview TSV is already prepared:

```powershell
.\.venv\Scripts\python.exe patcher\patcher.py --translation-preview path\to\encoded_preview.tsv --output rom\narutorpg3_chs_preview_test.nds
```

Every run writes a timestamped folder under `patcher/work/build_*` with `patcher.log`, generated text/font assets, the ROM work directory, and `patcher-build-summary.json`.

When rebuilding from translations, structure audit failures, missing font characters, fixed-slot overflow, or non-ready menu translation rows stop the build.
