# Story Autoskip Safe Code Probe

## Symptom

After bypassing the name validation failure, the early story text could auto-skip and display incorrectly.

## Current Hypothesis

The full writeback code table uses `0xF040..0xFAAB`, emitted as bytes like:

```text
F0 40 F0 41 ...
```

Menu rendering accepts this range, but the story/message interpreter appears to treat `F0`-prefixed bytes differently from ordinary visible Shift-JIS-like text. That can explain both symptoms:

- incorrect visible text;
- automatic message advance or skipped story text.

This means the title/menu overlay success does not prove the same code range is safe for story message streams.

## Probe Build

Generated a low-lead-byte SJIS-shaped table starting at `0x8840`:

```text
plan/cache/text-writeback-smoke/code-table-safe-8840/zh_code_table.tsv
plan/cache/text-writeback-smoke/code-table-safe-8840/encoded_preview.tsv
plan/cache/text-writeback-smoke/code-table-safe-8840/overlay_menu_translations.tsv
plan/cache/text-writeback-smoke/font-build-safe-8840/
```

Allocation result:

```text
start_code=0x8840
code_shape=sjis
entry_count=1986
collisions=0
```

Built:

```text
rom/narutorpg3_chs_full_writeback_menu_safe8840_no_friend_kinshi_v1.nds
```

This ROM also excludes:

```text
msg/wifi/friend_msg.msg
msg/wifi/kinshi_msg.msg
```

Static verification:

- `ndstool -i` reports Header CRC OK and Banner CRC OK.
- first full-writeback story/tutorial row changed from `F0 40 ...` to `88 40 ...`.
- menu overlay translations were re-encoded with the same `0x8840` code table.

An alternate `0x9040` probe was also built to reduce the chance of colliding with original font entries:

```text
plan/cache/text-writeback-smoke/code-table-safe-9040/
plan/cache/text-writeback-smoke/font-build-safe-9040/
rom/narutorpg3_chs_full_writeback_menu_safe9040_no_friend_kinshi_v1.nds
plan/cache/text-writeback-smoke/full-writeback-menu-safe9040-no-friend-kinshi-v1-records.json
```

Static verification:

- `ndstool -i` reports Header CRC OK and Banner CRC OK.
- first full-writeback story/tutorial row starts with `90 40 ...`.
- menu overlay translations were re-encoded with the same `0x9040` code table.

## Needed Runtime Check

Load first:

```text
rom/narutorpg3_chs_full_writeback_menu_safe8840_no_friend_kinshi_v1.nds
```

Then create a new save and check the early story. If it no longer auto-skips, the `0xF0xx` range should be marked unsafe for story/message text and the `0x8840`-range table should become the next baseline.

If the story still displays wrong glyphs or still skips, test:

```text
rom/narutorpg3_chs_full_writeback_menu_safe9040_no_friend_kinshi_v1.nds
```

If both low-range builds still auto-skip, the next target is not only code range selection; inspect the story message parser and the fixed-slot zero-fill/padding policy.

## Structure-Safe Writeback Finding

User-provided expected first story line confirms the first visible text in `msg/fld/evt/000.m` does not start at row offset `0x10`; it starts after a small script prefix:

```text
source_file=msg/fld/evt/000.m
offset=0x10
raw prefix=41 00 00 00 02 02 00 00 46 00
first visible quote=81 75
original first terminator=03 00 at file offset 0x60
```

The dumped row had treated this prefix as visible text/control text, so old full writeback replaced too much. The old `safe9040_no_friend_kinshi` build also moved the first `03 00` terminator from `0x60` to `0x3A` and then zero-filled the remaining slot. In these `.m` message streams, bytes after `03 00` are parsed as the next script command, so moving the terminator forward can corrupt flow and produce automatic skipping.

The text writeback builder now uses a structure-safe policy for `category=message` rows with raw `03 00` terminators:

- preserve bytes before the first original opening quote `81 75`;
- remove leading dump artifacts such as synthetic `A{CTRL_0000}...` from the replacement text;
- keep the final `03 00` at the original source-slot position;
- pad remaining unused payload before the terminator with `81 40` full-width spaces instead of zero bytes after an early terminator.

Static byte check for the first story row:

```text
origin term=0x60:
41 00 00 00 02 02 00 00 46 00 81 75 ... 03 00 02 00 01 05 ...

old safe9040_no_friend_kinshi term=0x3A:
00 00 00 02 02 00 00 46 00 81 91 76 ... 03 00 00 00 00 ...

structsafe_v1 term=0x60:
41 00 00 00 02 02 00 00 46 00 F0 40 F1 59 ... 81 40 ... 03 00 02 00 01 05 ...

safe9040_structsafe_v1 term=0x60:
41 00 00 00 02 02 00 00 46 00 90 40 91 76 ... 81 40 ... 03 00 02 00 01 05 ...
```

Built runtime candidates:

```text
rom/narutorpg3_chs_full_writeback_menu_structsafe_v1.nds
plan/cache/text-writeback-smoke/full-writeback-menu-structsafe-v1-records.json

rom/narutorpg3_chs_full_writeback_menu_safe9040_structsafe_v1.nds
plan/cache/text-writeback-smoke/full-writeback-menu-safe9040-structsafe-v1-records.json
```

Both ROMs pass `ndstool -i` Header CRC OK and Banner CRC OK.

## Next Runtime Check

Test `rom/narutorpg3_chs_full_writeback_menu_structsafe_v1.nds` first. If the first story line no longer auto-skips, the root cause is confirmed as message stream structure/terminator placement. If it still displays wrong glyphs but does not skip, test `rom/narutorpg3_chs_full_writeback_menu_safe9040_structsafe_v1.nds` to separate code-range compatibility from message-flow corruption.
