# 阶段缓存：码表提取验证

更新时间：2026-06-02

## 验证项

冻结译文：

```text
rows=5863
chunks=322
freeze_issues=0
```

码表：

```text
entries=1986
range=0xF000..0xF7C1
collisions=0
```

manifest：

```text
entries=1986
matches_code_table=yes
```

控制 token 污染检查：

```text
Select-String text\code_table\zh_charset.txt,text\code_table\zh_code_table.tsv -Pattern '\{CTRL_|CTRL_'
result=none
```

font-dir 冒烟：

```text
build_vram_font_files.py result=ok
chs_1x1.map magic=CHMP
chs_1x1.chunk magic=CHP1
chs_1x2.map magic=CHMP
chs_1x2.chunk magic=CHP2
```

## 结论

码表提取、编码分配、manifest 生成和 font-dir 构建冒烟已完成。当前产物可交接给后续文本编码替换与 ROM 回写计划。

剩余风险：

- 1x1/1x2 模式仍为 provisional。
- 普通 ASCII 当前未进入中文扩展码表。
- font-dir 构建成功不代表游戏内显示正确。
- 后续必须处理文本回写编码、控制符保留、长度限制、指针扩容和 ROM 验证。
