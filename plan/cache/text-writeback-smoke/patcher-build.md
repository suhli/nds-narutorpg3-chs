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

## v5 regression follow-up

- `rom/narutorpg3_chs_patcher_v6_regression_staticfix.nds` adds two missed fixed UI rows: `overlay_0000:0x30270` and `overlay_0003:0x450A0`. It also selectively includes the two safe save-name display rows from `msg/wifi/friend_msg.msg` while keeping the validation-sensitive friend/kinshi rows excluded. `patcher/tools/ndstool.exe -i` reported Header CRC OK and Banner CRC OK.
- Dialogue message padding is now zero-filled before the original `03 00` terminator instead of full-width-space-filled. This keeps the terminator at the original slot end while avoiding blank dialogue pages caused by visible padding.
- `zh_txt_6b929156_0006CE_0023` (`msg/fld/evt/001.m:0x6CE`) had a bad source parse: raw `50 00` plus following Japanese text was represented as `P{CTRL_8200}...`. Added a source-text override and manual Chinese override so the row now encodes `CTRL_0001 CTRL_0101 CTRL_0050` plus `退下！`.
- Rebuilt adjusted previews in both `plan/cache/text-writeback-smoke/` and `patcher/resources/text/`; audit result remains `after_control_mismatch_rows=0`, `overflow_rows=0`, `missing_char_rows=0`.
- Latest ROM: `rom/narutorpg3_chs_patcher_v8_msg_zerofill_dialogfix_fusion12.nds`, built from `patcher/work/build_20260603_212844`. `patcher/tools/ndstool.exe -i` reported Header CRC OK and Banner CRC OK. Missing chars remain only `U+E0FD` in `1x1.ttf` and `1x2.ttf`; text/menu missing counts are 0.
- `rom/narutorpg3_chs_patcher_v9_yesno_structsafe_fusion12.nds` adds structure-safe handling for field-message yes/no option prefixes. Rows beginning with raw `はい{CTRL_0001}いいえ` now keep the following binary/script tail at the original byte offsets by writing `是　{CTRL_0001}否　　`; mixed option-prefix-plus-dialogue rows translate the prefix in place and only rewrite the later dialogue payload.
- `rom/narutorpg3_chs_patcher_v10_yesno_binfragfix_fusion12.nds` additionally excludes three obvious non-text fragments from full writeback: `zh_txt_a346a806_0031E1_0180`, `zh_txt_579f0fbf_0029AD_0181`, and `zh_txt_c741b6bc_003795_0263`. Static byte checks confirmed those ranges are unchanged from `patcher/work/origin_unpacked` in the v10 workdir.
- v10 verification: `patcher/tools/ndstool.exe -i` reported Header CRC OK / Banner CRC OK; text_rows=5842, menu_rows=287. Missing chars remain only `U+E0FD` in bundled `1x1.ttf` and `1x2.ttf`, with text/menu missing counts both 0.
- `rom/narutorpg3_chs_patcher_v13_itemget_emptylinefix_fusion12.nds` adds row-level text overrides in the writeback tool. Thirteen generic item-acquisition suffix rows now write `{CTRL_0001}获得了！`, keeping item-name variables before the page break; four trailing-`{CTRL_0001}` rows are rewritten so they no longer create a final blank message page.
- v13 verification: `patcher/tools/ndstool.exe -i` reported Header CRC OK / Banner CRC OK. Static byte checks compared 17 override rows in `patcher/work/build_20260603_223946/rom_work/data/text` against the writeback function output and found `bad_count=0`. Missing chars remain only `U+E0FD` in bundled `1x1.ttf` and `1x2.ttf`, with text/menu missing counts both 0.
- `rom/narutorpg3_chs_patcher_v14_itemget_emptyline_menupunct_fusion12.nds` additionally replaces the remaining save-file menu `・` characters with Chinese `·` in four overlay_0003 rows and updates their encoded bytes from `81 45` to `F1 CB`.
- v14 verification: `patcher/tools/ndstool.exe -i` reported Header CRC OK / Banner CRC OK. Static byte checks found all 17 text override rows and all 4 menu punctuation rows matched the rebuilt workdir bytes. Missing chars remain only `U+E0FD` in bundled `1x1.ttf` and `1x2.ttf`, with text/menu missing counts both 0.
- User runtime testing invalidated v14 as a stable baseline: zero-filled message tails caused all story dialogue to auto-advance, translated embedded yes/no records still froze save points, and the two combined status-field translations rendered as repeated fallback glyphs.
- `rom/narutorpg3_chs_patcher_v15_runtime_stability_fusion12.nds` is the stability-first recovery build. It restores full-width-space padding before original message terminators, excludes all seven embedded yes/no records, and marks `menu_overlay_0000_030270` plus `menu_overlay_0003_0450A0` as blocked null-delimited rows.
- v15 verification: `patcher/tools/ndstool.exe -i` reported Header CRC OK / Banner CRC OK; text_rows=5835 and menu_rows=285. All seven yes/no ranges and both blocked menu ranges match `patcher/work/origin_unpacked` byte-for-byte. The first story record keeps its terminator at the original relative offset and its final 32 pre-terminator bytes are all `81 40`.
- v15 build command: `.\.venv\Scripts\python.exe -B patcher\patcher.py --output rom\narutorpg3_chs_patcher_v15_runtime_stability_fusion12.nds`. The build used immutable input `rom/origin.nds`, cached extraction `patcher/work/origin_unpacked`, and timestamped work directory `patcher/work/build_20260604_095616`.
