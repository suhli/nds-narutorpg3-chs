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

## Inspect

```powershell
.\.venv\Scripts\python.exe -B patcher\patcher.py info
.\.venv\Scripts\python.exe -B patcher\patcher.py verify-data
```

Expected final ROM:

- Version: `v36-no-pre03-spaces`
- SHA256: `B29FEA1B5B7BBD5E2010BD5AF1262676B6B71CB1D6E126847BECCB9A71954BB9`
- Status: user verified OK
