# v27 固定槽位填充与 overlay 模板修复

## 背景

用户手测 v26 后继续反馈 5 类问题：

- 获取道具提示仍显示日文。
- 少量对话仍出现乱码或提前结束。
- 战斗胜利结果页仍有日文大字和字段。
- 部分道具说明仍在半句后显示乱码或 `@`。
- 电影/剧场版说明快速结束。

本轮仍按用户约定只做静态排查、字节核对和回包，不启动 DeSmuME/MCP。

## 静态根因

1. 获取道具提示不在普通文本表内，而在 `overlay/overlay_0002.bin` 的固定模板区 `0x12C80..0x12DB0`。
   该区使用 `%s/%c` 运行时占位符和 `01 FF`、`03 FF` 控制字节，不是普通 `{CTRL_0001}` / `03 00` 消息流。旧写回只覆盖了普通 overlay 菜单行，没有覆盖这些模板后缀，所以仍显示 `はいっていた！` / `てにいれた！`。

2. 道具、忍术、装备、技能和体调效果说明表不能继续把 `00 00 00 00` 当成“翻译后立即结束并零填充”的通用规则。
   在这些表里，原始 `NUL4` 更接近固定可见槽位边界；翻译后用 `00` 补满会被部分界面渲染为 `@` 或乱码。v27 改为在原始 `NUL4` 前用全角空格补齐，保留原始边界。

3. `param/*.dat` 的名字槽位没有文本终止符，是固定宽度可见槽位。
   这些名字槽位不能用 `00` 补齐，否则会在列表、商店或菜单中截断或显示异常。v27 统一改为全角空格补齐。

4. 没有普通终止符、也没有已识别场景尾控制的 message 行，必须仍按 message 规则做可见字符规范化。
   v26 之前的固定槽位路径会直接使用 preview 编码，可能留下半角 ASCII 或 `00` padding；v27 对所有 `category == "message"` 的固定槽位路径重新走 `normalized_message_text`，并使用全角空格 padding。

5. 战斗结果截图中的 `せんとうけっか`、`かくとく...` 等关键字在 v27 workdir 的 CP932 扫描中已经没有命中。
   这部分大概率不是当前普通文本/overlay CP932 字符串，而是图形、layout 或特殊 HUD 资源；本轮不把它误判为普通文本写回问题。

6. 追加对原版和 v27 workdir 的 LZ10 解压后 CP932 扫描，`せんとうけっか`、`かくとくけいけんち`、`かくとくしたしのび札・アイテム`、`せんとうランク` 等仍为 0 命中。
   因此这些大字标签不是“压缩明文漏扫”，而是 baked 图块、tile-index layout 或特殊 HUD 字块。

## 修改内容

- `patcher/tools/build_text_writeback_smoke_rom.py`
  - `msg/item_msg.msg`、`msg/jyutu_msg.msg`、`msg/equip_msg.msg`、`msg/skill_msg.msg`、`msg/taityou_kouka.msg` 从“提前 NUL4 终止并零填充”规则中移除。
  - `category == "message"`、固定槽位说明表、`param/` 固定名字表统一支持全角空格 padding。
  - 固定槽位 message 路径统一重新规范化可见文本，避免半角 ASCII 或错误 padding 进入文本流。

- `tools/build_text_writeback_smoke_rom.py`
  - 与 patcher 版本同步。

- `patcher/tools/build_full_writeback_menu_overlay_rom.py`
  - 新增 `overlay_0002.bin:0x12C80..0x12DB0` 模板区二进制替换。
  - 保留 `%s/%c`、`01 FF`、`03 FF` 等运行时占位符和控制字节。
  - 将 `%sが` / `%sを` 后的日文助词替换为全角空格，避免显示残留。
  - 将 `はいっていた！`、`てにいれた！`、`もちものが　いっぱいです！` 替换为中文短句并按原字节宽度补齐。

- `tools/build_full_writeback_menu_overlay_rom.py`
  - 与 patcher 版本同步。

## 候选 ROM

```text
rom/narutorpg3_chs_patcher_v27_static_control_slot_padding.nds
SHA256 AD2FD6BD45C9D5C70DDADF4F3C19563BC66AF3555DB8A583A3B924F3792D3B41
```

构建目录：

```text
patcher/work/build_20260605_174557
```

## 验证结果

- `patcher.py` 构建完成，文本缺字 0，菜单缺字 0；字体仍仅保留预期占位符 `U+E0FD`。
- `ndstool -i`：Header CRC OK / Banner CRC OK。
- 结构审计：
  - `plan/cache/text-writeback-smoke/v5-regression-20260603/v27-static-control-slot-padding-audit.json`
  - `risk_rows=0`
- 实际 workdir 逐字节核对：
  - `plan/cache/text-writeback-smoke/v5-regression-20260603/v27-static-control-slot-padding-byte-compare.json`
  - `text_checked=5858`
  - `text_mismatch_count=0`
  - `menu_checked=289`
  - `menu_mismatch_count=0`
- overlay 模板写回：
  - `row_count=5`
  - `replacement_count=16`
  - `%sが`: 4 处
  - `%sを`: 2 处
  - `はいっていた！`: 5 处
  - `てにいれた！`: 3 处
  - `もちものが　いっぱいです！`: 2 处
- v27 workdir 关键日文残留扫描命中 0：
  - `はいっていた！`
  - `てにいれた！`
  - `もちものが　いっぱいです！`
  - `せんとうけっか`
  - `かくとくしたしのび札・アイテム`
  - `すこしかいふく`
  - `ひょうろうがん`
  - `えいが`
- 追加静态资源定位：
  - 原版未压缩/压缩后 CP932 扫描：`せんとうけっか`、`かくとくけいけんち`、`かくとくしたしのび札・アイテム`、`せんとうランク` 均为 0 命中。
  - `data/system/b*.c/.s/.p` 背景渲染未定位到战斗结果红字板。
  - `data/system/o*.n + .c/.t` OAM 帧渲染确认 o 系列为 OBJ 小帧，当前未定位到该结果页红字。
  - `data/b_char/common/*.t` tile sheet 预览未定位到该结果页红字。

## 当前结论

v27 已覆盖本轮反馈中可静态定位到普通文本、固定槽位和 overlay 模板的同类问题。需要用户手测确认的重点：

- 获取道具提示是否已中文化。
- 道具/忍术/装备说明是否不再出现 `@` 或半句后乱码。
- 电影/剧场版说明是否不再快速结束。
- 对话乱码点是否消失。

战斗胜利结果页的大字标题和部分日文字段，本轮静态未在普通文本、overlay CP932、LZ10 解压 CP932、system BG/OAM 预览中定位到。当前按 baked 图块、tile-index layout 或特殊 HUD 资源继续排查，不并入 v27 文本控制符修复范围。
