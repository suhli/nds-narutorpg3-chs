# v29 CTRL_0001 换行结论修正

## 背景

用户在 v28 手测中指出示例对白：

```text
「这里的甜栗相当有名{CTRL_0001}我也是从波之国来买的哦」
```

游戏内实际显示为两行正文：

```text
「这里的甜栗相当有名
我也是从波之国来买的哦」
```

这说明该处 `{CTRL_0001}` 不是空页，而是普通对白里的显式换行或换页推进控制。不能把所有前后都有正文的 `{CTRL_0001}` 自动删除。

## 静态字节观察

记录定位：

```text
id=zh_txt_dc122c8a_000DAA_0047
source_file=msg/fld/029.m
offset=0xDAA
source_len=106
terminator=03 00
```

当前 v28 写回策略下：

```text
encoded_len=46
encoded_ctrl_0100_positions=[20]
padding_len=58
padding_strategy=fullwidth_space_fill_before_original_terminator
terminator_position=preserved_original_end
```

也就是说，译文中的 `01 00` 正好对应两行之间的换行；译文结束后到原始末尾 `03 00` 之前还有 58 字节 `81 40` 全角空格填充。

## 修正结论

- v28 的空页修复规则仍然成立：只删除 leading/trailing/consecutive/control-only 的 `{CTRL_0001}` 空页。
- 非空正文之间的 `{CTRL_0001}` 不能按空页处理。
- 当前截图中的“空白感”更可能来自短译文后的全角空格填充被文字解释器继续消耗，而不是 `{CTRL_0001}` 本身错误。
- 下一轮 v29 不采用“合并普通中间 `{CTRL_0001}`”方案；应改为研究 message 记录尾部填充的可替代策略，目标是在不移动原始 `03 00` 结构位置、不恢复 v14 自动跳过问题的前提下，减少可见空白或等待空白。

## 后续验证方向

- 全量枚举 `message_padding_len > 0` 的普通 `message` 记录，按来源、填充长度、是否含 `{CTRL_0001}` 分类。
- 保持原始 `03 00` 位置不变，寻找比 `81 40` 更适合作为“安全消耗填充”的字节或控制序列。
- 任何候选策略都必须先通过静态结构核对；运行时效果继续交给用户手动验证，不使用 DeSmuME/MCP。
