# 阶段缓存：冻结译文输入

更新时间：2026-06-02

## 输入口径

冻结输入只读取：

```text
text/translation/chunks/index.json
text/translation/chunks/translated/<chunk_id>.tsv
text/translation/chunks/reports/<chunk_id>-control-code-check.json
```

不读取 `text/translation/zh_translation.tsv`，因为当前主表 `zh_text` 全为空。

不按 glob 直接读取全部 translated 文件；旧空文件 `chunk_0292.tsv`、`chunk_0293.tsv`、`chunk_0294.tsv` 不在当前 index 中，已排除。

## 修正记录

冻结前发现两个 translated chunk 行多出一个空 TSV 字段：

```text
text/translation/chunks/translated/chunk_0107.tsv
text/translation/chunks/translated/chunk_0136.tsv
```

已只修正字段分隔和句尾 padding 空格，不改变译文本身。随后重新运行对应 chunk 校验：

```text
chunk_0107: rows=6 checked=6 issues=0
chunk_0136: rows=80 checked=80 issues=0
```

并刷新进度：

```text
chunks=322 translated=322 validated=322 issues=0
```

## 冻结命令

```text
.\.venv\Scripts\python.exe -B tools\extract_translation_charset.py --start-code 0xF040 --code-shape sjis
```

## 冻结结果

```text
chunks=322
rows=5863
freeze_issues=0
```

产物：

```text
text/code_table/frozen_translation.tsv
text/reports/code-table-summary.json
```

`code-table-summary.json` 记录了每个有效 chunk 的路径、行数、校验报告和 SHA-1。
