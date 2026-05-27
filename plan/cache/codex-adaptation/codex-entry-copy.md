# 阶段缓存：Codex 入口复制

## 当前阶段

阶段：复制并适配 Codex 入口。

状态：已完成。

## 缓存上下文

用户要求“复制一份 subagents/skills，claude.md 以适配 codex”。

检查结果：

- `.claude/skills/` 存在。
- `.claude/subagents/` 不存在。
- `.claude/agents/` 不存在。
- `CLAUDE.md` 存在。
- `.codex/` 和 `AGENTS.md` 此前不存在。

## 本阶段处理

- 复制 `.claude/skills/` 到 `.codex/skills/`。
- 创建 `AGENTS.md` 作为 Codex 项目说明入口。
- 将 Codex 侧文档中的 `.claude/skills/...` 路径替换为 `.codex/skills/...`。
- 更新 `plan/state.yaml` 指向 `plan/codex-adaptation.md`。

## 后续恢复入口

新对话应先读：

- `plan/state.yaml`

然后按其中的 `current_plan.document` 读取：

- `plan/codex-adaptation.md`
