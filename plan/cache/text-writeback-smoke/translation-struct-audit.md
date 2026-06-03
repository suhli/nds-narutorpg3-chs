# Translation Structure Audit

## Goal

After `rom/narutorpg3_chs_full_writeback_menu_structsafe_v1.nds` was manually verified to enter the first story dialogue, the next risk was translation text still containing dump artifacts or mismatched message controls.

This pass audits the active writeback preview rather than `text/translation/zh_translation.tsv`, because the ROM build currently uses:

```text
text/writeback/encoded_preview.tsv
```

## Script

Added:

```text
tools/audit_structsafe_translations.py
```

The script derives an adjusted source text per row:

- quote-prefixed message rows preserve bytes before the first original `81 75` quote;
- `xx 00 + SJIS text` message rows preserve the `xx 00` prefix and compare only the actual text payload;
- fixed-length NUL padding is not treated as required `{CTRL_0000}` text;
- translations are checked against the adjusted source control-token sequence.

Outputs:

```text
plan/cache/text-writeback-smoke/translation-struct-audit-report.json
plan/cache/text-writeback-smoke/translation-struct-mismatches.tsv
plan/cache/text-writeback-smoke/translation-struct-manual-overrides.tsv
plan/cache/text-writeback-smoke/encoded-preview-struct-adjusted.tsv
```

## Result

Final audit result:

```text
checked_rows=5843
excluded_rows=20
auto_adjusted_rows=1009
manual_override_rows=5
after_control_mismatch_rows=0
overflow_rows=0
missing_char_rows=0
```

The 20 excluded rows remain the known save/name-validation exclusions:

```text
msg/wifi/friend_msg.msg: 19
msg/wifi/kinshi_msg.msg: 1
```

The 5 manual overrides are item-acquisition message fragments where the dump had misread a message prefix as high control tokens. They were normalized to a short `{CTRL_0001}获得了！`-style payload so the real `CTRL_0001` is preserved.

## Rebuilt ROM

Built from the adjusted preview:

```text
rom/narutorpg3_chs_full_writeback_menu_structaudit_v1.nds
rom/unpacked/narutorpg3_chs_full_writeback_menu_structaudit_v1/
plan/cache/text-writeback-smoke/full-writeback-menu-structaudit-v1-records.json
```

Build summary:

```text
text_rows=5843
menu_rows=278
copy_hook_size=0x10C
```

Static verification:

- `ndstool -i` reports Header CRC OK and Banner CRC OK.
- `msg/fld/evt/000.m` first story line still keeps `03 00` at offset `0x60`.
- `msg/fld/005.m` offset `0xC6` now keeps the `30 00` message prefix and writes `01 00` before the translated acquisition text.

## Next Runtime Check

Test:

```text
rom/narutorpg3_chs_full_writeback_menu_structaudit_v1.nds
```

Primary checks:

- first story dialogue still does not auto-skip;
- item/acquisition messages do not break flow;
- highlighted words do not show stray `{CTRL_xxxx}` artifacts;
- save creation remains valid because wifi friend/prohibited-word text is still excluded.
