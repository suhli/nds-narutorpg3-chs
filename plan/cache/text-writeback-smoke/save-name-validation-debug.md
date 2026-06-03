# Save Name Validation Debug

## Symptom

After building the full text/menu writeback ROM, the new-save name input screen could reject an entered kana name and show:

```text
这个名字无法登录！
请使用其他名字。
```

The displayed Chinese message maps to the original text in `msg/wifi/friend_msg.msg` at `0x47C`:

```text
そのなまえは　とうろくできません！{CTRL_0001}べつのなまえを　つけてください
```

## Finding

The adjacent source file `msg/wifi/kinshi_msg.msg` is a prohibited-word/name-validation list. It contains one large `{CTRL_0000}`-separated list such as:

```text
ぶっとばす{CTRL_0000}げんばく{CTRL_0000}...
```

The previous full-writeback build treated this file as ordinary display text and translated it. That is unsafe because the name validator still compares input against the original CP932 kana-oriented table.

## Fix

`tools/build_text_writeback_smoke_rom.py` now defaults to excluding:

```text
msg/wifi/friend_msg.msg
msg/wifi/kinshi_msg.msg
```

`tools/build_full_writeback_menu_overlay_rom.py` uses the same default exclusion for full menu ROM builds.

`friend_msg.msg` is also held back because the new-save name path reuses the Wi-Fi/user-profile name registration messages. Keeping only `kinshi_msg.msg` original was not enough: v2 still rejected valid kana names.

## Verification

Built:

```text
rom/narutorpg3_chs_full_writeback_menu_v2.nds
```

Records:

```text
plan/cache/text-writeback-smoke/full-writeback-menu-v2-records.json
```

Static verification:

- `text_rows=5862`, one fewer than v1 because `msg/wifi/kinshi_msg.msg` was skipped.
- `excluded_source_files={"msg/wifi/kinshi_msg.msg": 1}`.
- `rom/unpacked/narutorpg3_chs_full_writeback_menu_v2/data/text/msg/wifi/kinshi_msg.msg` SHA-1 equals the original unpacked file.
- v1 did not match the original prohibited-word file.
- `ndstool -i rom/narutorpg3_chs_full_writeback_menu_v2.nds` reports Header CRC OK and Banner CRC OK.

Follow-up isolation builds:

```text
rom/narutorpg3_chs_full_writeback_menu_no_wifi_text_v1.nds
rom/narutorpg3_chs_full_writeback_menu_no_friend_kinshi_v1.nds
```

The user confirmed that the later test could enter the game, so `friend_msg.msg` and `kinshi_msg.msg` should stay excluded until the name validator is separately mapped.

## Follow-Up

Runtime confirmation is still needed on the real DeSmuME window: load `rom/narutorpg3_chs_full_writeback_menu_v2.nds`, create a new save, enter a multi-kana test name, and confirm the validation message no longer appears for valid names.
