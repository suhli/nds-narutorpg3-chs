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
- default 1x1 and 1x2 TTF files

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

- Default build produced `rom/narutorpg3_chs_patcher_default_test.nds`; `tools/ndstool.exe -i` reported Header CRC OK and Banner CRC OK.
- Rebuild from bundled frozen translation produced `rom/narutorpg3_chs_patcher_rebuild_text_test.nds`; text audit reported `after_control_mismatch_rows=0`, `missing_char_rows=0`, and `overflow_rows=0`.
- Explicit `--font-1x1`/`--font-1x2` build produced `rom/narutorpg3_chs_patcher_font_arg_test.nds`; `tools/ndstool.exe -i` reported Header CRC OK and Banner CRC OK.
- Repeated-output rebuild test produced `rom/narutorpg3_chs_patcher_rebuild_text_test_build_20260603_151144.nds`, proving the patcher now selects an unused output path before invoking the lower-level builder.
- Menu rebuild report for the repeated-output test had `ready=278`, no pending keys, and no missing font chars.

## ROM safety

- `rom/origin.nds` remains read-only.
- The patcher unpacks to `patcher/work/origin_unpacked` if needed.
- Each build uses a timestamped `patcher/work/build_*` directory.
- Repacked ROMs are written only to the requested output path and then checked with `tools/ndstool.exe -i`.
