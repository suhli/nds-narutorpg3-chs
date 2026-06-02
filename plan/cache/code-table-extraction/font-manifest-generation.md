# 阶段缓存：字体 manifest 生成

更新时间：2026-06-02

## 输入

```text
text/code_table/zh_code_table.tsv
```

## 输出

```text
text/code_table/font_manifest.json
text/code_table/font_manifest.txt
```

JSON manifest 使用 `tools/build_vram_font_files.py` 支持的字段：

```json
{
  "entries": [
    {
      "code": "0xF040",
      "char": "「",
      "modes": ["1x1", "1x2"]
    }
  ]
}
```

文本 manifest 格式：

```text
0xF040 「 1x1,1x2
```

## 注意事项

码表中包含全角空格等空白字符。`tools/build_vram_font_files.py` 当前会对 manifest 的 `char` 字段执行 `strip()`，因此 manifest 生成器会把空白字符写成 `\uXXXX` 形式，避免被解析为空字符。

结果：

```text
manifest_entries=1986
manifest_matches_code_table=yes
```
