# 初始候选 dump 结果

## 执行入口

```text
tools/dump_text_candidates.py
```

执行命令：

```text
.\.venv\Scripts\python.exe -B tools\dump_text_candidates.py
```

`-B` 用于避免写入 `tools/__pycache__`。当前环境中 `py_compile` 写 `.pyc` 会遇到 `WinError 5` 权限问题，但脚本本体可正常运行。

## 输出

```text
text/original/jp_dump.tsv
text/translation/zh_translation.tsv
text/reports/text_candidate_summary.json
text/reports/control-code-check.json
```

## 结果摘要

本轮扫描范围：

```text
rom/unpacked/origin/data/text
```

扫描扩展名：

```text
.bin,.dat,.m,.msg,.s,.scr
```

结果：

```text
files_scanned=595
candidate_count=6174
message=3976
param=2198
message:m=3139
message:msg=837
param:dat=2198
```

## 解码策略

- `msg` 类资源使用消息流候选解码。
- CP932/SJIS 文本直接解码。
- 常见控制词保留为 `{CTRL_xxxx}`。
- `03 00` 作为常见消息结束锚点，导出为 `CTRL_0003`。
- `00 00 00 00` 作为固定字符串或记录边界候选。
- `param` 类资源暂时使用 CP932/SJIS run 扫描，先保留候选偏移。

## 当前质量判断

这不是最终回写级 dump，而是可翻译前置候选 dump：

- `msg/*.m` 与 `msg/*.msg` 已能保留控制词和消息结束锚点。
- `param/*.dat` 已能抽出大量名称、术、道具、说明类候选文本，但结构边界仍需建模。
- `script/*.s` 当前没有进入结果摘要，抽样看更像指令/指针结构，不直接进入翻译表。
- 仍有少量 `message_stream_stopped_at_unknown_byte`，需要在控制符建模阶段处理。

## 下一步

1. 对 140 条 `message_stream_stopped_at_unknown_byte` 做控制符归类。
2. 建立 `.m/.msg` 头部字段和记录边界说明。
3. 建立 `param/*.dat` 的固定字段/固定宽度文本结构，避免把二进制字段误当文本。
4. 翻译只能先填 `zh_translation.tsv` 中候选条目的 `zh_text`，冻结基线前必须通过控制符校验。

## 控制符校验

当前译文表还没有填入 `zh_text`，校验脚本可运行：

```text
rows=6174
checked_translated_rows=0
issue_count=0
```
