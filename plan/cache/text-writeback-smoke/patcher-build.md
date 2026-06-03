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

## ROM safety

- `rom/origin.nds` remains read-only.
- The patcher unpacks to `patcher/work/origin_unpacked` if needed.
- Each build uses a timestamped `patcher/work/build_*` directory.
- Repacked ROMs are written only to the requested output path and then checked with `tools/ndstool.exe -i`.
