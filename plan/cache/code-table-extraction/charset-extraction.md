# 阶段缓存：字符集提取

更新时间：2026-06-02

## 命令

```text
.\.venv\Scripts\python.exe -B tools\extract_translation_charset.py --start-code 0xF000
```

## 过滤规则

- 只统计冻结 TSV 的 `zh_text`。
- 忽略 `{CTRL_xxxx}` 控制 token。
- 忽略行尾 ASCII padding 空格。
- 普通 ASCII 单独统计到 `ignored_ascii.txt`，默认不进入中文扩展码表。
- 保留中文、中文标点、日文式标点、全角数字/字母和实际显示符号。
- 按首次出现顺序冻结字符顺序。

## 结果

```text
unique_charset=1986
ignored_ascii_total=1877
control_token_literal_in_charset=0
```

产物：

```text
text/code_table/zh_charset.txt
text/code_table/ignored_ascii.txt
text/reports/code-table-summary.json
```

`ignored_ascii.txt` 中记录了半角空格、数字、字母、`Wi-Fi`、按钮字母等 ASCII 出现情况；这些字符后续是否进入回写编码，需要在文本回写阶段按显示需求单独决定。
