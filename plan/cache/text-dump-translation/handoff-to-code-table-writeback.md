# 文本 dump 与翻译基线 handoff

更新时间：2026-06-02

## 交接结论

`text-dump-translation` 计划已完成到可交接给码表提取阶段的状态。后续不在本计划内生成码表、字模、文本回写或 ROM。

后续当前计划：

```text
plan/code-table-extraction.md
```

## 可用译文输入

当前可用译文位于：

```text
text/translation/chunks/translated/*.tsv
```

有效 chunk 清单必须以如下文件为准：

```text
text/translation/chunks/index.json
```

当前统计：

```text
chunks=322
rows=5863
translated_chunks=322
validated_chunks=322
translated_rows=5863
aligned_rows=5863
issue_count=0
```

来源：

```text
text/translation/chunks/progress.json
```

## 禁止使用的输入

当前主表：

```text
text/translation/zh_translation.tsv
```

有 5863 行，但 `zh_text` 全为空。它不能作为码表提取输入。

对主表运行 `tools/check_translation_table.py` 只能得到：

```text
rows=5863 checked=0 issues=0
```

该结果只说明没有非空译文可检查，不代表主表已经可用于码表提取。

## 旧空 chunk

以下旧空译文文件存在，但不在当前 `index.json` 中：

```text
chunk_0292.tsv
chunk_0293.tsv
chunk_0294.tsv
```

后续工具不得按 glob 直接读取全部 translated chunk；必须按 `index.json` 逐项读取。

## 控制符规则

译文中的控制 token 形如：

```text
{CTRL_xxxx}
```

码表提取时：

- 不统计控制 token 本身。
- 保留控制 token 顺序供后续文本回写使用。
- `CTRL_0003` 作为记录终止符继续由原 dump/回写流程处理，不进入 `zh_text` 字符集。
- 高亮、变量、分页、换行相关控制词不得在码表阶段改写。

## 交接给码表计划的输入口径

码表计划应先冻结合并 TSV：

```text
text/code_table/frozen_translation.tsv
```

冻结输入只来自：

```text
text/translation/chunks/index.json
text/translation/chunks/translated/<chunk_id>.tsv
```

后续字符集、码表、manifest、font-dir 冒烟都基于该冻结文件。

## 后续风险

- 码表默认起点 `0xE000` 需要冲突扫描后再冻结。
- 1x1/1x2 字模模式目前只能先标记为 provisional。
- 半角 ASCII 先单独统计，不默认进入中文扩展码表。
- 码表阶段不解决文本回写长度、指针扩容、文本池迁移或 ROM 验证。
