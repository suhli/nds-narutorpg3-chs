# 翻译基线分块进度

## 当前状态

本阶段从 `text/translation/zh_translation.tsv` 切分出分块翻译输入：

```text
text/translation/chunks/index.json
text/translation/chunks/source/
```

当前规模：

```text
rows=6174
chunks=325
```

已完成并通过本地增强校验的首批 chunk：

```text
chunk_0001
chunk_0002
chunk_0003
chunk_0004
chunk_0005
chunk_0006
chunk_0007
chunk_0008
chunk_0009
chunk_0010
chunk_0011
chunk_0012
chunk_0013
chunk_0014
chunk_0015
chunk_0016
chunk_0017
chunk_0018
chunk_0019
chunk_0020
chunk_0021
chunk_0022
chunk_0023
chunk_0024
chunk_0025
chunk_0026
chunk_0027
chunk_0028
chunk_0029
chunk_0030
```

进度汇总入口：

```text
text/translation/chunks/progress.json
```

最近一次汇总：

```text
chunks=325
translated=30
validated=30
issues=0
translated_rows=163
```

## 质量门槛

每个译文 chunk 必须同时满足：

- 保留每行全部 `{CTRL_xxxx}` token，顺序不变。
- `zh_text` 的序列化长度严格等于 `source_byte_len`：控制符 token 按原始 2 字节控制字计，其余译文按 UTF-8 字节计。
- 不使用 ASCII `?`、乱码、罗马音或摘要占位。
- 高亮 span 中的术语 payload 不得被清空。
- 多个 `{CTRL_0001}` 分隔出的句段需要逐段保留语义。
- 如果源文有人名、称呼、条件句、动作对象或按钮名，译文需要对应体现。
- 如果源文包含汉字术语后的假名注音，注音忽略，不写入译文。

结构检查入口：

```text
tools/check_translation_table.py
```

进度汇总入口：

```text
tools/summarize_translation_chunks.py
```

## 当前阻塞与处理

原计划使用多个 `gpt-5.3-codex` translation-worker 并行翻译，但当前会话里的部分 worker 已触发用量限制。后续继续时先由主线本地处理小 chunk，并在 worker 恢复可用后再恢复并行分派。

已分派但需要主线接管/复核的 chunk：

```text
chunk_0006
chunk_0007
chunk_0008
chunk_0009
chunk_0010
```

`chunk_0006`、`chunk_0007`、`chunk_0008` 已由主线重写并通过校验；`chunk_0009` 制作人员表与 `chunk_0010` 结尾提示也已完成并通过校验。`chunk_0011` 到 `chunk_0030` 已继续完成，其中 `chunk_0011` 到 `chunk_0019`、`chunk_0021`、`chunk_0023`、`chunk_0025` 为短系统文本，`chunk_0020` 到 `chunk_0030` 为电影支线对白。

本轮修正：

- 修正 `tools/check_translation_table.py` 的长度模型：`source_byte_len` 来自原始 `raw_hex`，不能把 `{CTRL_0001}` 这类占位文本按 11 个 UTF-8 字节计算。
- 纯标点感叹行不再强制要求译文包含 CJK，避免把 `……！？` 这类有效译文误判为缺中文。
- 已重新补齐 `chunk_0001` 到 `chunk_0008` 的尾部 padding，并生成 `chunk_0009`、`chunk_0010` 的校验报告。

## 下一步

1. 从 `chunk_0031` 继续向后翻译。
2. 每批完成后跑 `tools/check_translation_table.py` 校验每个 chunk。
3. 跑 `tools/summarize_translation_chunks.py` 更新 `progress.json`。
4. 当前小批次稳定后，再合并回 `text/translation/zh_translation.tsv`。
