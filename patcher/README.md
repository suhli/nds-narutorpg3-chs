# Naruto RPG3 Chinese Patcher

This directory now contains the final verified patch state in one data file and one CLI.

## Files

- `patcher.py`: single stdlib-only command line tool.
- `narutorpg3_chs_v36.json`: consolidated project data. It contains the verified final ROM image, source/output hashes, translation rows, menu rows, manual overrides, and static writeback audit summaries.

Historical build scripts, generated work directories, intermediate text assets, and old ROM variants are intentionally not required for the final build.

## Build

```powershell
.\.venv\Scripts\python.exe -B patcher\patcher.py --output rom\narutorpg3_chs.nds
```

The default command is `build`, so the command above is equivalent to:

```powershell
.\.venv\Scripts\python.exe -B patcher\patcher.py build --output rom\narutorpg3_chs.nds
```

The CLI validates `rom/origin.nds` against the stored SHA256 before writing the final ROM. It refuses to overwrite `rom/origin.nds`.

If the target output already exists, the CLI writes a timestamped sibling unless `--force` is passed.

## Custom Fonts

The verified ROM embeds two Chinese glyph chunks:

- `font/chs_1x1.chunk`: 8x8 / 1x1 glyphs.
- `font/chs_1x2.chunk`: 8x16 / 1x2 glyphs.

You can rebuild the ROM with replacement TTF/TTC/OTF fonts while keeping the verified text, code table, maps, hooks, and NitroFS layout unchanged:

```powershell
.\.venv\Scripts\python.exe -B patcher\patcher.py --font-8x8 path\to\8px.ttf --font-8x16 path\to\12px.ttf --output rom\narutorpg3_chs_font_test.nds
```

Font rebuilding is driven by the fixed table at `patcher/resources/text/zh_code_table.tsv`. The CLI validates that this table matches the embedded `CHMP` maps, then rebuilds the `CHP1` / `CHP2` chunks with the original resident/source page layout. Do not rebuild the table from translation order when swapping fonts.

Replace only one mode:

```powershell
.\.venv\Scripts\python.exe -B patcher\patcher.py --font-8x8 path\to\8px.ttf --output rom\narutorpg3_chs_font_8x8_test.nds
.\.venv\Scripts\python.exe -B patcher\patcher.py --font-8x16 path\to\12px.ttf --output rom\narutorpg3_chs_font_8x16_test.nds
```

Use one font for both modes:

```powershell
.\.venv\Scripts\python.exe -B patcher\patcher.py --font path\to\font.ttf --output rom\narutorpg3_chs_font_test.nds
```

Font replacement requires Pillow in the active Python environment. Install it with `uv pip install pillow` when setting up a fresh `.venv`. Local `.ttf`, `.ttc`, and `.otf` files are ignored by git.

## Inspect

```powershell
.\.venv\Scripts\python.exe -B patcher\patcher.py info
.\.venv\Scripts\python.exe -B patcher\patcher.py verify-data
```

## BPS Patch

Generate a standard BPS patch from `rom/origin.nds` to the verified v36 ROM:

```powershell
.\.venv\Scripts\python.exe -B patcher\make_bps.py
```

Default output:

```text
dist/narutorpg3_chs_v36.bps
```

The BPS script verifies the patch by applying it back to `rom/origin.nds` in memory and comparing the rebuilt ROM to the verified v36 target. Use `--no-verify` only when you intentionally want to skip that check.

Expected final ROM:

- Version: `v36-no-pre03-spaces`
- SHA256: `B29FEA1B5B7BBD5E2010BD5AF1262676B6B71CB1D6E126847BECCB9A71954BB9`
- Status: user verified OK
