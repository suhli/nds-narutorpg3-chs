# 阶段缓存：编码分配与冲突扫描

更新时间：2026-06-02

## 初始尝试

按计划先尝试默认起点：

```text
start_code=0xE000
```

冲突扫描发现 2 个 raw text word 冲突：

```text
暴 -> 0xE34A
蛙 -> 0xE5B3
```

因此没有冻结 `0xE000` 方案。

## 中间分配

改用：

```text
start_code=0xF000
```

结果：

```text
entry_count=1986
start_code=0xF000
end_code=0xF7C1
collision_count=0
```

文本回写预检发现 `0xF000..0xF7C1` 连续分配中有 541 个码点不符合 SJIS 双字节形状，且 8 个码点低字节为 `00`。该方案不再作为最终冻结方案。

## 最终分配

改用 SJIS 形状分配：

```text
start_code=0xF040
code_shape=sjis
```

结果：

```text
entry_count=1986
start_code=0xF040
end_code=0xFAAB
collision_count=0
skipped_code_count=1
skipped_code=0xFA40 raw_text_word
sjis_shape_invalid=0
low_byte_zero=0
```

码表字段：

```text
char
unicode_hex
code_hex
modes
frequency
first_seen_chunk
first_seen_row
source_count
notes
```

当前 `modes` 统一为：

```text
1x1,1x2
```

`notes` 统一为：

```text
provisional
```

原因是本阶段还没有逐文本显示模式来源，不能过早收窄 1x1/1x2。

产物：

```text
text/code_table/zh_code_table.tsv
```
