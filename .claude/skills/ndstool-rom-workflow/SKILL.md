---
name: ndstool-rom-workflow
description: Use this project skill when unpacking, inspecting, or repacking the NDS ROM with tools/ndstool.exe; always preserve rom/origin.nds and build modified output as a separate ROM.
---

# ndstool ROM Workflow

## Core Rules

- Use the repository-local tool at `tools/ndstool.exe`. If a request says `ndstools.exe`, treat it as referring to the existing `tools/ndstool.exe` unless a different file is added later.
- Treat `rom/origin.nds` as immutable source material. Never overwrite it, patch it in place, or use it as the output path for repacking.
- Put extracted working files under a separate work directory, for example `rom/unpacked/origin/` or another clearly named directory.
- Put rebuilt ROMs under `rom/` with a new filename, for example `rom/narutorpg3_chs.nds`, `rom/test_font_patch.nds`, or another task-specific name.
- Before destructive cleanup of extracted files, verify the resolved target path is under the intended work directory.

## Inspect ROM

Use this before planning extraction or repacking:

```powershell
.\tools\ndstool.exe -i rom\origin.nds
.\tools\ndstool.exe -l rom\origin.nds
.\tools\ndstool.exe -l rom\origin.nds -v
```

## Unpack ROM

Create a dedicated extraction directory, then extract the ROM components into it:

```powershell
.\tools\ndstool.exe -x rom\origin.nds `
  -9 rom\unpacked\origin\arm9.bin `
  -7 rom\unpacked\origin\arm7.bin `
  -y9 rom\unpacked\origin\y9.bin `
  -y7 rom\unpacked\origin\y7.bin `
  -d rom\unpacked\origin\data `
  -y rom\unpacked\origin\overlay `
  -t rom\unpacked\origin\banner.bin `
  -h rom\unpacked\origin\header.bin
```

If a task uses a different extraction directory, keep the same component layout so repacking remains mechanical.

## Repack ROM

Build a new ROM path. Do not use `rom/origin.nds` as the `-c` target.

```powershell
.\tools\ndstool.exe -c rom\narutorpg3_chs.nds `
  -9 rom\unpacked\origin\arm9.bin `
  -7 rom\unpacked\origin\arm7.bin `
  -y9 rom\unpacked\origin\y9.bin `
  -y7 rom\unpacked\origin\y7.bin `
  -d rom\unpacked\origin\data `
  -y rom\unpacked\origin\overlay `
  -t rom\unpacked\origin\banner.bin `
  -h rom\unpacked\origin\header.bin
```

Use a task-specific output filename when producing temporary verification builds.

## After Repacking

- Run `tools/ndstool.exe -i <new-rom>` to confirm the rebuilt ROM is readable.
- If manual binary edits require it, run `tools/ndstool.exe -f <new-rom>` only on the rebuilt ROM, never on `rom/origin.nds`.
- Record the unpack/repack command, input directory, output ROM name, and verification result in `plan/`.
