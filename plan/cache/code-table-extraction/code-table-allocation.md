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

## 最终分配

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
