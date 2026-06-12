# v28 空白页控制符全量修复

## 背景

用户手测 v27 后反馈仍有底部对白框空白，需要全量修复空行/空页问题。本轮继续遵守手测约定，只做静态排查、字节核对和回包，不启动 DeSmuME/MCP。

## 根因

文本流中的 `{CTRL_0001}` 是换页/换行类控制。旧规则只保留控制符数量和原始终止符边界，没有统一处理以下空白页形态：

- 译文以 `{CTRL_0001}` 开头，首屏没有可见文字。
- 译文以 `{CTRL_0001}` 结尾，末尾多出一个空白确认页。
- 译文中存在 `{CTRL_0001}{CTRL_0001}`，中间形成纯空页。
- 某些页只包含颜色/样式控制符，没有可见文字。

裸字节扫描 `01 00` 会误判 `{CTRL_0103}{CTRL_0000}` 的交叉字节，因此本轮改为按文本控制符解析，而不是在替换字节中直接找 `01 00`。

## 修改

- `patcher/tools/build_text_writeback_smoke_rom.py`
  - 新增 `trim_blank_ctrl0001_pages()`。
  - `message` 文本编码前删除/合并没有可见字符的 `{CTRL_0001}` 页面。
  - 对纯控制符空页，保留非 `{CTRL_0001}` 控制符并移动到相邻可见页，避免丢失颜色、样式或场景尾控制。
  - 固定 `CTRL_0000` 子槽位继续按原始子槽位原位写回；子槽内允许去除纯空白 `{CTRL_0001}` 页，但仍核对非换页控制符序列。
- `tools/build_text_writeback_smoke_rom.py`
  - 与 patcher 版本同步。
- `patcher/tools/audit_v24_structural_risks.py` 和 `tools/audit_v24_structural_risks.py`
  - 审计改为按 trim 后文本检查空白 `{CTRL_0001}` 页，作为后续回归门槛。

## 全量影响

`v28-blankline-trim-report.json` 记录本轮实际 trim 了 76 条 message：

- `leading_blank_page`: 41
- `interior_blank_page`: 28
- `consecutive_ctrl0001`: 27
- `trailing_blank_page`: 9

涉及来源主要包括：

- `msg/fld/034.m`: 24 条，主要是获取道具/给予道具类提示。
- `msg/btl/026.m`: 24 条，主要是电影/演职员表类固定槽位文本。
- `msg/fld/018.m`: 9 条，主要是同类获取道具提示。
- 其余为少量 `msg/fld/*`、`msg/fld/evt/*`、`msg/eiga/*`、`msg/wifi/*` 记录。

trim 后空白 `{CTRL_0001}` 页风险为 0。

## 候选 ROM

```text
rom/narutorpg3_chs_patcher_v28_blankline_trim.nds
SHA256 26427CFCAC8C1918AC4F3938764B6409F0BBD0B031B307F800C9B5C95DA4B3F6
```

构建目录：

```text
patcher/work/build_20260611_222831
```

## 验证

- `patcher.py` 构建完成；文本缺字 0，菜单缺字 0；字体仍仅保留既有占位符 `U+E0FD`。
- `ndstool -i rom/narutorpg3_chs_patcher_v28_blankline_trim.nds`：Header CRC OK / Banner CRC OK。
- 结构审计：
  - `plan/cache/text-writeback-smoke/v5-regression-20260603/v28-blankline-structural-audit.json`
  - `risk_rows=0`
  - `blank_ctrl0001_page_row_count=0`
- 实际 workdir 逐字节核对：
  - `plan/cache/text-writeback-smoke/v5-regression-20260603/v28-blankline-byte-compare.json`
  - `text_checked=5858`
  - `text_mismatch_count=0`
  - `menu_checked=289`
  - `menu_mismatch_count=0`
  - `overlay_template_checked=5`
  - `overlay_template_mismatch_count=0`

## 当前结论

v28 已把当前资源表中所有可静态识别的 `{CTRL_0001}` 空白页风险清零，并保留固定子槽位和 overlay 模板结构。运行时显示仍由用户手动验证；本轮未使用 DeSmuME/MCP。
