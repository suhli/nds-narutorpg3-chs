# Patcher build handoff

## Context

The full writeback/menu build has a verified structure-safe baseline:

- `rom/narutorpg3_chs_full_writeback_menu_structsafe_v1.nds` was manually verified by the user to enter story dialogue.
- `rom/narutorpg3_chs_full_writeback_menu_structaudit_v1.nds` was rebuilt from `plan/cache/text-writeback-smoke/encoded-preview-struct-adjusted.tsv` with no final control mismatches, overflow rows, or missing characters.

## Patcher scope

Created `patcher/` as a frozen patching bundle for the current baseline.

Static resources copied into `patcher/resources/`:

- frozen translation TSV, code table, charset, font manifest
- structure-adjusted encoded preview and manual structure overrides
- menu candidates and ready menu translations
- default 1x1 and 1x2 TTF files, named `patcher/resources/fonts/1x1.ttf` and `patcher/resources/fonts/1x2.ttf`

Bundled build tools copied into `patcher/tools/`:

- the 20 Python scripts in the patcher dependency closure
- `ndstool.exe`, required for unpacking, repacking, and verification
- `.gitignore` now explicitly unignores `patcher/tools/**` and bundled TTF files while keeping `patcher/tools/__pycache__/` ignored

Main entry point:

```text
patcher/patcher.py
```

Default output command:

```powershell
.\.venv\Scripts\python.exe patcher\patcher.py --output rom\narutorpg3_chs_patcher.nds
```

## Supported rebuild modes

- Default build: use frozen structaudit resources and regenerate font payloads from bundled TTFs.
- Font replacement: pass `--font`, or pass separate `--font-1x1` and `--font-1x2`.
- Translation replacement: pass `--translation-table`, or edit bundled `patcher/resources/text/frozen_translation.tsv` and pass `--rebuild-text-assets`.
- Direct preview replacement: pass `--translation-preview`.

## Verification

- Default build produced `rom/narutorpg3_chs_patcher_default_test.nds`; `patcher/tools/ndstool.exe -i` reported Header CRC OK and Banner CRC OK.
- Rebuild from bundled frozen translation produced `rom/narutorpg3_chs_patcher_rebuild_text_test.nds`; text audit reported `after_control_mismatch_rows=0`, `missing_char_rows=0`, and `overflow_rows=0`.
- Explicit `--font-1x1`/`--font-1x2` build produced `rom/narutorpg3_chs_patcher_font_arg_test.nds`; `patcher/tools/ndstool.exe -i` reported Header CRC OK and Banner CRC OK.
- Repeated-output rebuild test produced `rom/narutorpg3_chs_patcher_rebuild_text_test_build_20260603_151144.nds`, proving the patcher now selects an unused output path before invoking the lower-level builder.
- Menu rebuild report for the repeated-output test had `ready=278`, no pending keys, and no missing font chars.
- Bundled-tools build produced `rom/narutorpg3_chs_patcher_bundled_tools_test.nds`; logs show calls to `patcher/tools/build_vram_font_files.py`, `patcher/tools/build_full_writeback_menu_overlay_rom.py`, and `patcher/tools/ndstool.exe`. Header CRC and Banner CRC were OK.
- Missing characters are now warnings, not build blockers. Verified with `rom/narutorpg3_chs_patcher_missing_report_test_build_20260603_163222.nds`: build completed, Header CRC and Banner CRC were OK, and `patcher/work/build_20260603_163222/missing-chars-report.json` listed 418 missing TTF glyphs.
- Console missing-character output is now grouped by text/menu/font, and font misses are grouped by 1x1/1x2 with the missing TTF path. Verified with `rom/narutorpg3_chs_patcher_short_font_missing_console_test.nds`; `patcher/work/build_20260603_165100/missing-chars.tsv` includes `source`, `mode`, `char`, `unicode_hex`, `code`, and `font`.
- 1x2 rendering now uses an 8x12 target grid centered into 8x16 instead of compressing a 16x16 glyph to 8x16. Visual preview is `plan/cache/text-writeback-smoke/font-render-probe/1x2_candidate_fonts_compare.png`.
- `patcher/resources/fonts/1x2.ttf` now uses `fusion-pixel-12px-monospaced-zh_hans.ttf` by default per user request. `MZPXorig.ttf` remains as a comparison candidate. Verified builds `rom/narutorpg3_chs_patcher_mzpx_1x2_8x12_test.nds` and `rom/narutorpg3_chs_patcher_fusion12_1x2_8x12_test.nds`; both had Header CRC OK / Banner CRC OK and only `U+E0FD` missing.
- Added six manually delimited `overlay_0002` menu entries around `0x12C0C..0x12C72` for the item/equipment shop prompt. These rows patch only visible text bytes and intentionally leave the following `01 00` separators in place.
- Added a row-level override for `menu_overlay_0002_0128B8` so the item-acquisition suffix keeps the original 11 full-width placeholder spaces before `获得了！`.
- Fixed no-terminator UI text table padding for `msg/item_msg.msg`, `msg/equip_msg.msg`, `msg/jyutu_msg.msg`, `msg/menu/item_menu_msg.msg`, `msg/skill_msg.msg`, and `msg/taityou_kouka.msg`: shorter translations are now padded with full-width spaces instead of `00`, while embedded `{CTRL_0000}` separators remain encoded as `00 00`.
- Added manual `overlay_0003:0x43D64` menu entry for `だいじなもの -> 重要物`; the 16-byte slot is patched without clobbering the following `%s` format strings.
- Built `rom/narutorpg3_chs_patcher_v5_menu_itempad_fusion12.nds`; `patcher/tools/ndstool.exe -i` reported Header CRC OK and Banner CRC OK. The build used 5843 text rows and 285 menu rows. `patcher/work/build_20260603_184433/rom_work/data/text/msg/item_msg.msg` now shows `81 40` padding after the first short item description instead of `00` padding.
- Final v5 recheck at `2026-06-03T18:52:41+08:00`: AST syntax validation passed for the patcher scripts, `patcher/tools/ndstool.exe -i rom/narutorpg3_chs_patcher_v5_menu_itempad_fusion12.nds` still reports Header CRC OK / Banner CRC OK, `item_msg.msg:0x8` uses `81 40` padding, and `overlay_0003:0x43D64` preserves the following `%s` format strings.

## ROM safety

- `rom/origin.nds` remains read-only.
- The patcher unpacks to `patcher/work/origin_unpacked` if needed.
- Each build uses a timestamped `patcher/work/build_*` directory.
- Repacked ROMs are written only to the requested output path and then checked with `patcher/tools/ndstool.exe -i`.
