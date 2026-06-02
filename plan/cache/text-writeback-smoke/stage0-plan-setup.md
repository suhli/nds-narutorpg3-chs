# Stage 0: 计划接续与输入确认

更新时间：2026-06-02

## 状态

已完成。

## 已读取入口

```text
plan/state.yaml
plan/cache/code-table-extraction/handoff-to-text-writeback.md
```

## 接续结论

- 上一计划 `code-table-extraction` 已完成。
- 码表阶段产物可作为文本回写预览输入。
- 新计划为 `text-writeback-smoke`。
- 当前执行阶段切换为 `stage1-encoder-and-capacity`。

## 评审结论

计划评审 verdict 为 `accept`。

评审要求已写入计划正文和 state：

- Stage 1 必须在 `state.yaml` 中保留当前 plan、当前 stage、cache dir、cache 文档和主要产物路径。
- 中文码点端序不得默认，无法判断的行必须标记风险。
- `{CTRL_xxxx}` 的 little-endian u16 恢复只作为候选，进入样本前必须验证。
- ASCII 与 padding 风险必须隔离记录，不能静默修正。
- Stage 2 样本必须满足固定槽、容量、控制符、端序、ASCII、padding 和定位条件。
- Stage 3 输出必须是独立 ROM，不能覆盖 `rom/origin.nds`。
- Stage 4 的模拟器观察和新的逆向发现必须分别回写 `plan/cache/` 和 `hack/`。
