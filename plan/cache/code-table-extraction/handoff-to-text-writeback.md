# 码表提取到文本回写 handoff

更新时间：2026-06-02

## 当前完成产物

冻结译文：

```text
text/code_table/frozen_translation.tsv
```

字符集：

```text
text/code_table/zh_charset.txt
```

码表：

```text
text/code_table/zh_code_table.tsv
```

字体 manifest：

```text
text/code_table/font_manifest.json
text/code_table/font_manifest.txt
```

font-dir 冒烟输出：

```text
plan/cache/code-table-extraction/font-build-smoke/
```

报告：

```text
text/reports/code-table-summary.json
```

## 编码范围

```text
start_code=0xF000
end_code=0xF7C1
entry_count=1986
collision_count=0
```

`0xE000` 初始方案发现 raw text word 冲突，已废弃。

## 后续回写必须遵守

- 以 `frozen_translation.tsv` 为译文输入。
- 使用 `zh_code_table.tsv` 把可见中文和全角符号转换为新编码。
- `{CTRL_xxxx}` 控制 token 不按普通字符编码，必须恢复为原控制字节。
- 行尾 ASCII padding 是翻译对齐产物，后续回写要重新评估，不应盲目当作可见文本。
- 普通 ASCII 当前只统计在 `ignored_ascii.txt`，是否保留原编码或加入扩展码表，需要按显示路径决定。
- `modes=1x1,1x2` 仍是 provisional。
- 后续若执行 ROM 回写，必须输出新 ROM，不能覆盖 `rom/origin.nds`。

## 建议下一个计划

新建文本编码替换与 ROM 回写计划，阶段至少包含：

1. 中文编码器：`zh_text` + 控制 token -> 回写字节流。
2. 固定槽文本回写尝试与长度风险分类。
3. 超长文本的指针扩容、文本池迁移或脚本重排方案。
4. 集成 font-dir 与文本资源，重新打包新 ROM。
5. DeSmuME MCP 显示和流程验证。
