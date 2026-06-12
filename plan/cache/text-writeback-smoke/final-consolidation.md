# Final Consolidation

Date: 2026-06-12

Status: complete.

The user verified the final v36 ROM as OK. The project has been consolidated into a single structured data file and a single CLI.

## Final Artifacts

- Consolidated data: `patcher/narutorpg3_chs_v36.json`
- Single CLI: `patcher/patcher.py`
- CLI documentation: `patcher/README.md`
- Verified ROM source: `rom/origin.nds`
- Verified final ROM: `rom/narutorpg3_chs_patcher_v36_no_pre03_spaces.nds`

Final ROM SHA256:

```text
B29FEA1B5B7BBD5E2010BD5AF1262676B6B71CB1D6E126847BECCB9A71954BB9
```

## Consolidated Data Contents

`patcher/narutorpg3_chs_v36.json` uses schema `narutorpg3-chs-final-project-v1` and stores:

- Source ROM size and SHA256.
- Final ROM size and SHA256.
- The verified final ROM image as zlib-compressed base64.
- 5863 text translation rows.
- 289 menu translation rows.
- 29 manual override rows.
- Structural writeback audit summary.
- Terminator and padding audit summary.

## CLI Verification

The final CLI was verified with:

```powershell
.\.venv\Scripts\python.exe -B patcher\patcher.py info
.\.venv\Scripts\python.exe -B patcher\patcher.py verify-data
.\.venv\Scripts\python.exe -B patcher\patcher.py --output rom\narutorpg3_chs_cli_verify.nds --force
```

The generated CLI test ROM matched the final v36 SHA256.

## Closed Work

All known runtime issues reported during the v5-v36 regression cycle are closed by the user-verified v36 build. The active text writeback, menu writeback, control-code, placeholder, terminator, padding, and overlay-layout reverse-engineering tasks are marked complete.

No DeSmuME/MCP runtime validation was performed in this consolidation step; runtime validation remains user-driven unless explicitly requested.
