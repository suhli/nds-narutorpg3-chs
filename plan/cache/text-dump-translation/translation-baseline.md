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

重置前曾完成并通过本地增强校验的首批 chunk（仅作历史记录，当前译文已清空）：

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
chunk_0031
chunk_0032
chunk_0033
chunk_0034
chunk_0035
chunk_0036
chunk_0037
chunk_0038
chunk_0039
chunk_0040
chunk_0041
chunk_0042
chunk_0043
chunk_0044
chunk_0045
chunk_0046
chunk_0047
chunk_0048
chunk_0049
chunk_0050
chunk_0051
chunk_0052
chunk_0053
chunk_0054
chunk_0055
chunk_0056
chunk_0057
chunk_0058
chunk_0059
chunk_0060
chunk_0061
chunk_0062
chunk_0063
chunk_0064
chunk_0065
chunk_0066
chunk_0067
chunk_0068
chunk_0069
chunk_0070
chunk_0071
chunk_0072
chunk_0073
chunk_0074
chunk_0075
chunk_0076
chunk_0077
chunk_0078
chunk_0079
chunk_0080
chunk_0081
chunk_0082
chunk_0083
chunk_0084
chunk_0085
chunk_0086
chunk_0087
chunk_0088
chunk_0089
chunk_0090
chunk_0091
chunk_0092
chunk_0093
chunk_0094
chunk_0095
chunk_0096
chunk_0097
chunk_0098
chunk_0099
chunk_0100
chunk_0101
chunk_0102
chunk_0103
chunk_0104
chunk_0105
chunk_0106
chunk_0107
chunk_0108
chunk_0109
chunk_0110
chunk_0111
chunk_0112
chunk_0113
chunk_0114
chunk_0115
chunk_0116
chunk_0117
chunk_0118
chunk_0119
chunk_0120
chunk_0121
chunk_0122
chunk_0123
chunk_0124
chunk_0125
chunk_0126
chunk_0127
chunk_0128
chunk_0129
chunk_0130
chunk_0131
chunk_0132
chunk_0133
chunk_0134
chunk_0135
chunk_0136
chunk_0137
chunk_0138
chunk_0139
chunk_0140
chunk_0141
chunk_0142
chunk_0143
chunk_0144
chunk_0145
chunk_0146
chunk_0147
chunk_0148
chunk_0149
chunk_0150
chunk_0151
chunk_0152
chunk_0153
chunk_0154
chunk_0155
chunk_0156
chunk_0157
chunk_0158
chunk_0159
chunk_0160
chunk_0161
chunk_0162
chunk_0163
chunk_0164
chunk_0165
chunk_0166
chunk_0167
chunk_0168
chunk_0169
chunk_0170
chunk_0171
chunk_0172
chunk_0173
chunk_0174
chunk_0175
chunk_0176
chunk_0177
chunk_0178
chunk_0179
chunk_0180
chunk_0181
chunk_0182
chunk_0183
chunk_0184
chunk_0185
chunk_0186
chunk_0187
chunk_0188
chunk_0189
chunk_0190
chunk_0191
chunk_0192
chunk_0193
chunk_0194
chunk_0195
chunk_0196
```

进度汇总入口：

```text
text/translation/chunks/progress.json
```

最近一次汇总：

```text
chunks=325
translated=0
validated=0
issues=0
translated_rows=0
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

`chunk_0006`、`chunk_0007`、`chunk_0008` 已由主线重写并通过校验；`chunk_0009` 制作人员表与 `chunk_0010` 结尾提示也已完成并通过校验。`chunk_0011` 到 `chunk_0030` 已继续完成，其中 `chunk_0011` 到 `chunk_0019`、`chunk_0021`、`chunk_0023`、`chunk_0025` 为短系统文本，`chunk_0020` 到 `chunk_0030` 为电影支线对白。`chunk_0031` 到 `chunk_0099` 继续覆盖电影支线对白、短系统文本和少量候选边界截断行；截断行已保留控制符并在 `translator_note` 标注，`chunk_0056` 中的油女注音、`chunk_0058`/`chunk_0062` 中的修业注音已按规则忽略，`chunk_0073` 的乐符和结尾控制符已保留，`chunk_0080`/`chunk_0081`/`chunk_0085`/`chunk_0095`/`chunk_0098` 的高密度控制符演出已保留 token 并压缩可见文本，`chunk_0088`/`chunk_0089`/`chunk_0093`/`chunk_0094`/`chunk_0095`/`chunk_0098` 中的注音按规则忽略。`chunk_0100` 和 `chunk_0101` 已进入装备、防具说明短文本，译文按原字节长度压缩；`chunk_0102` 到 `chunk_0104` 覆盖武器、道具、忍札商店说明与复合菜单串，已保留高亮 token、菜单分隔控制符和是/否控制串。`chunk_0105` 到 `chunk_0112` 覆盖一乐、通灵伙伴、训练菜单、甘栗甘、花店、烤肉 Q、卡卡西照片说明等 NPC/场景文本；其中乐符控制符、变量控制符和候选边界残留已按规则保留或标注。`chunk_0113` 到 `chunk_0120` 覆盖影院菜单、医院场景、兑换券奖励、忍者学校和通灵纸说明文本；已保留高亮、菜单、变量和候选边界残留控制串，注音按规则忽略。`chunk_0121` 到 `chunk_0128` 覆盖木叶 NPC、对练道场说明、战斗教程、火影岩/破邪之谷剧情、短册街餐馆/旅店/商店文本；对练、阵形、查克拉蓄力、合体忍术等术语已统一。`chunk_0129` 到 `chunk_0132` 覆盖风影宅邸入口、木叶居民与商店解锁提示、温泉/亲热天堂支线、换人教程、“无”组织说明和暗部变量称呼文本；变量、高亮、乐符和注音均按规则处理。`chunk_0133` 到 `chunk_0135` 覆盖忍者学校/医院/火影宅邸 NPC、通灵术说明、短册街 NPC、砂隐村与砂隐商店菜单文本；砂隐、风影、通灵兽等术语已统一，菜单控制符已保留。`chunk_0136` 覆盖 Wi-Fi/通信对战规则与故乡手形、Wi-Fi 点数奖励文本；断行奖励短句和候选边界残留控制串按原结构保留。`chunk_0137` 到 `chunk_0140` 延续 Wi-Fi/无线通信奖励与交换说明，并覆盖替身术反击教程、起爆符/撒菱教程；候选边界残留控制串已压缩可见残留并保留控制符顺序。`chunk_0141` 到 `chunk_0144` 覆盖路牌、区域通行提示、通信对战开放提示、通灵宠物攀崖说明和卷轴移动点文本；地名与短教程术语已统一。`chunk_0145` 到 `chunk_0150` 覆盖短册街/水晶溪谷路牌、毒沼和水面通行教程、螺旋丸与忍识札说明、死亡沙漠规则以及自来也交付蛤蟆龙/蛤蟆吉的通灵宠物剧情；地名、人名、术名、通灵宠物与高亮控制符已统一处理。`chunk_0151` 到 `chunk_0159` 覆盖李的“毅力”麦克风桥段、封印提示、破邪之谷村庄检查、瞬身卷轴碎片、赤丸搬卷轴与兵粮丸/音效行；赤丸音效候选边界保留原控制串并压缩可见文本。`chunk_0160` 覆盖破邪之谷前史剧情，新增并统一桧木、娜兹娜、灵兽、邪气、镜子等术语，角色/表情控制串按原序保留。`chunk_0161` 到 `chunk_0162` 覆盖主线开场、娜兹娜求助、卡卡西出手与存档教程；鸣人、小樱、卡卡西、纲手、担当上忍、木叶标记、SELECT 键和保存等术语已写入术语表。`chunk_0163` 到 `chunk_0172` 由 worker 分派产出初稿，主线验收修复问号占位、错译和可见控制前缀后通过校验；覆盖灵兽说明、破邪镜任务、破邪之谷入口/高速移动地图教程、邪气扩散、鹿丸/井野/丁次入队、丁次肉弹战车、鹿丸影子模仿术和六角/玄翔剧情；新增术语写入术语表。`chunk_0173` 到 `chunk_0184` 继续采用 worker 初稿加主线验收，主线重译了 0173-0178 的错译/占位行并修正 0182 的牙台词；覆盖破邪镜陷阱、再不斩/白幻影、镜中陷阱规则、水晶溪谷任务、牙/志乃/雏田救援、查克拉绳索与小蛞蝓教程；新增术语写入术语表。`chunk_0185` 到 `chunk_0196` 由 worker 分块翻译后主线验收，主线修复了 0185-0187 的口癖直译/引号风格/可见控制残留、0189 的我爱罗注音残留和 0192 的错译；覆盖雏田白眼照明、小洞赤丸侦查、第三面镜子陷阱、中忍考试会场幻影、回木叶汇报、砂隐村/死亡沙漠入口、小李破岩和宁次回天；新增术语写入术语表。

本轮修正：

- 修正 `tools/check_translation_table.py` 的长度模型：`source_byte_len` 来自原始 `raw_hex`，不能把 `{CTRL_0001}` 这类占位文本按 11 个 UTF-8 字节计算。
- 纯标点感叹行不再强制要求译文包含 CJK，避免把 `……！？` 这类有效译文误判为缺中文。
- 已重新补齐 `chunk_0001` 到 `chunk_0008` 的尾部 padding，并生成 `chunk_0009`、`chunk_0010` 的校验报告。

本轮质量修正：

- 已清空 `chunk_0001` 到 `chunk_0196` 已完成译文中的 `translator_note` 和 `qa_note` 工作流残留；这些字段不再承载 prompt、验收或候选 dump 说明。
- 已补强 `tools/check_translation_table.py`：`translator_note`/`qa_note` 中的工作流词、以及译文开头可见控制字节残留会被计为 `text_quality_issues`。
- 已批量清理 180 行译文开头的可见 dump 残留字节，例如 `6{CTRL...}u`、`@{CTRL...}u`、`` `{CTRL...}@``；所有修改均按 `source_byte_len` 补空格保持字节级对齐。
- 重新校验 `chunk_0001` 到 `chunk_0196`：`translated=196`、`validated=196`、`issues=0`；工作流残留扫描结果为 0。

本轮重置与脚本化翻译：

- 按用户要求废弃并清空全部既有译文：`text/translation/zh_translation.tsv`、`text/translation/chunks/source/*.tsv`、`text/translation/chunks/translated/*.tsv` 的 `zh_text`、`translator_note`、`qa_note` 已清空，`status` 重置为 `pending_translation`，`length_risk` 重置为 `unknown`。
- 旧的 `candidate dump`、`todo_candidate_boundary`、`confirm boundary`、`prompt`、`worker` 等残留已从翻译相关 TSV 中清除；当前非空译文行数为 0。
- 新增 `tools/batch_translate_chunks_openai.py`，从工程根目录 `.env` 加载 OpenAI 兼容接口配置，按 chunk 批量请求 `/chat/completions`，提示词内置当前控制符、字节级对齐、注音忽略、上下文翻译和大陆译名规则。
- `tools/summarize_translation_chunks.py` 已调整为只把存在非空译文的 chunk 计入 translated；当前进度已重置为 `chunks=325`、`translated=0`、`validated=0`、`issues=0`。

## 下一步

1. 在工程根目录 `.env` 配置 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`，或使用 `OPENAI_COMPAT_API_KEY`、`OPENAI_COMPAT_BASE_URL`、`OPENAI_COMPAT_MODEL`。
2. 从 `chunk_0001` 开始运行 `tools/batch_translate_chunks_openai.py` 批量翻译；建议先小批量跑 `--start chunk_0001 --limit-chunks 1`。
3. 每个 chunk 写出后默认运行 `tools/check_translation_table.py` 校验，并由脚本调用 `tools/summarize_translation_chunks.py` 更新 `progress.json`。
4. 当前脚本化流程稳定后，再合并回 `text/translation/zh_translation.tsv`。
