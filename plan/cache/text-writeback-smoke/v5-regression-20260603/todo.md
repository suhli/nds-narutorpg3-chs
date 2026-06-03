# v5 回归问题待办

## 基线

- 测试 ROM：`rom/narutorpg3_chs_patcher_v5_menu_itempad_fusion12.nds`
- 记录时间：`2026-06-03`
- 截图目录：`plan/cache/text-writeback-smoke/v5-regression-20260603/`

## 待办清单

1. [ ] 部分对话仍会卡死。
   - 截图：`issue-01-dialogue-freeze-symbols.jpg`
   - 现象：对话框显示一排异常横线/符号后流程可能卡住。
   - 初步方向：优先查该行是否把变量/等待/结束控制符编码成了普通可见字形，或把原结束符位置破坏。

2. [ ] 保存覆盖确认框里“是”已翻译，但“否”不见了，颜色看起来也不对。
   - 截图：`issue-02-save-confirm-yes-no.jpg`
   - 现象：选项框只看到红色“是”，未看到“否”。
   - 初步方向：查保存确认相关 overlay 菜单槽位，确认是否覆盖了 `01 00`/颜色/选项分隔控制字节。

3. [ ] 部分对话仍有符号残留，疑似原本应引用角色名或变量。
   - 截图：`issue-03-dialogue-variable-symbol-tail.jpg`
   - 现象：句末出现类似 `C`/方框的残留符号。
   - 初步方向：查原文同位置是否含变量控制符；禁止把这类控制符当作普通文本翻译或压缩。

4. [ ] 升级时的状态变化仍未翻译。
   - 截图：`issue-04-level-up-status-untranslated.jpg`
   - 现象：升级界面中 `レベル`、`スタミナ`、`チャクラ`、`こうげき` 等仍为日文。
   - 初步方向：优先扫 battle/result/level-up 相关 overlay 或固定 UI 资源，不一定在当前 text/msg 全量表内。

5. [ ] 战斗完成后的界面仍有未翻译文本。
   - 截图：`issue-05-battle-result-untranslated.jpg`
   - 现象：战斗结果页标题、字段、掉落物名等大量日文残留。
   - 初步方向：同第 4 项，扫战斗结果 overlay/参数表/固定 UI 字符串。

6. [ ] 释放忍术时的战斗 UI 仍有未翻译文本。
   - 截图：`issue-06-jutsu-battle-ui-untranslated.jpg`
   - 现象：`じんけいなし`、攻击/防御字段、查克拉提示、操作提示等仍为日文。
   - 初步方向：扫战斗 HUD/忍术演出相关 overlay，确认是否是图片字、overlay 字符串或另一路字体表。

7. [ ] 教程仍有空行。
   - 截图：`issue-07-tutorial-empty-line.jpg`
   - 现象：说话人名显示，但正文为空。
   - 初步方向：查对应教程消息是否被 trim 到空文本，或控制符/换页符位置导致正文被跳过。

8. [ ] 对话存在未翻译内容。
   - 截图：`issue-08-untranslated-dialogue.jpg`
   - 现象：正文中混有日文 `ひっこめろ！`。
   - 初步方向：定位该日文所在资源；确认是否为未抽取文本、翻译表漏项，还是变量/控制符附近被跳过。

9. [ ] 对话仍有空行。
   - 截图：`issue-09-dialogue-empty-line.jpg`
   - 现象：鸣人头像和说话人名显示，但正文为空。
   - 初步方向：同第 7 项，优先对空正文候选做结构审计，保留原结束符位置。

10. [ ] 创建存档时的提示未翻译。
    - 截图：`issue-10-save-name-created-untranslated.jpg`
    - 截图：`issue-10-save-name-command-help-untranslated.jpg`
    - 现象：名字输入完成提示、用户命令说明仍为日文。
    - 初步方向：查名字输入/保存系统消息资源，可能不在当前 overlay 菜单翻译表内。

## 当前排查顺序

1. 先静态定位截图中仍可读的日文字符串和异常符号来源。
2. 再分两类处理：文本结构问题优先修控制符/结束符；未翻译 UI 优先补扫描和菜单/overlay 回写。
3. 每修一类构建一个新 ROM，避免一次混入过多不确定修改。
