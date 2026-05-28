---
name: translation-worker
description: Translate Naruto RPG3 dumped Japanese text into Simplified Chinese with glossary management, context-aware chunk handling, and byte-length aligned output.
---

# Translation Worker

## Runtime

Use model `gpt-5.3-codex` when this worker is spawned.

## Scope

Translate chunked rows from:

```text
text/translation/chunks/source/
```

Write translated chunks to:

```text
text/translation/chunks/translated/
```

Maintain the glossary at:

```text
text/translation/glossary.tsv
```

Do not update `plan/`, `plan/state.yaml`, or any `plan/cache/` file during translation work.

## Translation Rules

- Use Simplified Chinese.
- Follow common Mainland China Naruto translation habits.
- Keep names, jutsu, locations, UI terms, and recurring battle terms consistent through `text/translation/glossary.tsv`.
- Before translating a chunk, inspect adjacent rows in that chunk. If consecutive rows form one dialogue, tutorial, menu flow, or sentence, translate them together for context.
- Preserve every `{CTRL_xxxx}` token in the same order as the source row.
- `CTRL_0003` appears as the row terminator field and should not be inserted into the translated sentence unless it already appears inside `jp_text`.
- Ignore Japanese ruby/furigana glosses. Common pattern: a kanji term followed by parentheses containing kana. Translate the kanji term only; do not translate or preserve the kana reading in the Chinese output.
- Do not invent missing context. Mark uncertain cases in `translator_note`.

## Byte Alignment

Each row has `source_byte_len`.

For `zh_text`, output a string whose UTF-8 byte length is exactly `source_byte_len`.

- If the Chinese translation is shorter, pad the end with ASCII spaces.
- If it is too long, shorten the translation while preserving meaning and all `{CTRL_xxxx}` tokens.
- Do not drop control tokens to fit the budget.
- If exact alignment is impossible, leave the best translation, set `status=needs_fit`, and explain in `translator_note`.

## Glossary

The glossary file is TSV with:

```text
jp_term	zh_cn_term	category	notes	source_ids
```

When encountering a recurring name, jutsu, place, UI command, item, or battle concept:

1. Reuse an existing glossary entry if present.
2. Add a new entry if none exists.
3. Prefer established Mainland Chinese Naruto usage.
4. Record representative row IDs in `source_ids`.

Seed conventions:

```text
ナルト	鸣人	character
サスケ	佐助	character
サクラ	小樱	character
カカシ	卡卡西	character
木ノ葉	木叶	place
チャクラ	查克拉	term
忍術	忍术	term
術	术	term
口よせ	通灵	term
影分身	影分身	term
写輪眼	写轮眼	term
螺旋丸	螺旋丸	term
火遁	火遁	term
手裏剣	手里剑	item
こうげき	攻击	ui
いどう	移动	ui
コマンド	指令	ui
バトル	战斗	ui
ターン	回合	ui
ダメージ	伤害	term
```

## Output Requirements

For each translated chunk:

- Keep the same delimiter and header as the source chunk.
- Fill `zh_text`.
- Set `status` to `translated_aligned` when byte length and control-token checks pass.
- Set `length_risk` to `ok`, `tight`, or `needs_fit`.
- Set `context_required` to `no` unless follow-up context is still needed.
- Use `translator_note` only for uncertainty, context gaps, fit compromises, or glossary decisions.

After each chunk, run the local translation checker if available:

```text
.\.venv\Scripts\python.exe -B tools\check_translation_table.py --translation <translated-chunk> --out <chunk-report>
```
