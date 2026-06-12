# CTRL_0001 换行与 message 尾部填充

## 结论

`{CTRL_0001}` 在普通对白中可以作为显式换行或换页推进控制使用。不能仅因为它前后都有正文就删除。

示例：

```text
zh_txt_dc122c8a_000DAA_0047
msg/fld/029.m:0xDAA
「这里的甜栗相当有名{CTRL_0001}我也是从波之国来买的哦」
```

用户运行时截图显示为两行正文：

```text
「这里的甜栗相当有名
我也是从波之国来买的哦」
```

因此该处 `{CTRL_0001}` 是正常换行，不是空页。

## 与空页修复的边界

可以自动清理的 `{CTRL_0001}` 形态：

- 开头空页：`{CTRL_0001}` 前没有可见正文。
- 结尾空页：`{CTRL_0001}` 后没有可见正文。
- 连续空页：`{CTRL_0001}{CTRL_0001}`。
- 只包含颜色/样式控制符、没有可见正文的控制页。

不能自动清理的形态：

- 前后都是可见正文的普通换行。
- 多页教程、列表、片尾字幕、颜色/高亮结构分段。
- 紧邻 `{CTRL_0103}`、`{CTRL_0002}`、`{CTRL_0000}` 等结构控制符的分段。

## 尾部填充风险

当前结构安全 message 写回为了避免 v14 的自动跳过问题，会把原始 `03 00` 保持在原槽位末尾。短译文后剩余容量使用 `81 40` 全角空格填充。

对示例记录的静态观察：

```text
source_len=106
encoded_len=46
padding_len=58
padding_strategy=fullwidth_space_fill_before_original_terminator
terminator_position=preserved_original_end
```

如果运行时出现“文字已结束但仍有空白等待/空白区域”的体感，优先怀疑尾部 `81 40` 填充被文字解释器继续消耗，而不是正文中间的 `{CTRL_0001}` 错误。

## v29 变长候选补充

用户随后确认可以接受“不再强制对齐原文长度，只保留一个终止符”的候选方向。写回器因此新增显式开关 `--compact-message-terminators`。

该候选不再保留普通 message 记录中原始 `03 00` 的物理位置，而是将终止符移动到译文后，并删除中间的 `81 40` 全角空格填充：

```text
prefix + encoded_text + 81 40 padding + 03 00
prefix + encoded_text + 03 00
```

这会改变目标 message 文件内后续内容的 offset，因此只作为手测候选，不替代默认 v28 固定长度写回。详细记录见：

```text
plan/cache/text-writeback-smoke/v5-regression-20260603/v29-compact-msg-terminators.md
hack/v29_message变长终止符压缩候选.md
```

手测结果显示 v29 会导致所有对话卡死，说明普通 message 不能直接缩短文件。

## v30 固定长度早停补充

v30 改为保持原始槽位长度，只把普通 `03 00` 提前到译文后面，然后用全角空格填充剩余槽位：

```text
prefix + encoded_text + 03 00 + 81 40 padding
```

该分支由 `--early-message-terminator-fullwidth-fill` 启用，详细记录见：

```text
plan/cache/text-writeback-smoke/v5-regression-20260603/v30-early03-fullwidth-fill.md
hack/v30_message固定长度早停03全角填充候选.md
```

## 后续方向

后续候选修复应研究 `message` 尾部填充，而不是合并非空 `{CTRL_0001}`。当前有两条分支：

- 默认分支：继续保留原始 `03 00` 位置，寻找比 `81 40` 更安全的填充字节或控制序列。
- v29 失败分支：不再保持原文槽位长度，删除填充并只保留译文后的 `03 00`；手测导致所有对话卡死。
- v30 候选分支：保持原文槽位长度，把 `03 00` 提前到译文后，再用全角空格填充剩余槽位。
