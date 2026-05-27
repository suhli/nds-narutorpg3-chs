# 阶段缓存：计划入口重构

## 当前阶段

阶段：计划入口重构。

状态：已完成。

## 缓存上下文

用户指出此前把每个计划写成独立 YAML state 是错误方向。正确结构应该是：

- `plan/state.yaml` 或 `plan/state.json` 是统一状态入口。
- state 中直接写当前进行的 plan 文档地址。
- state 中直接写目前进行到哪个阶段。
- state 中直接写阶段缓存文档的目录和具体地址。
- 具体 plan 用 `.md` 组织，需要有背景和必要上下文。

## 本阶段处理

- 更新 `CLAUDE.md` 的计划状态管理规则。
- 新增 `plan/state.yaml`。
- 新增 `plan/project-guidance.md` 作为当前项目协作说明计划正文。
- 新增 `plan/desmume-mcp-skill.md` 作为 DeSmuME MCP skill 计划正文。
- 删除旧的 `plan/claude-md-project-guidance.yaml` 和 `plan/desmume-mcp-skill.yaml`。

## 后续恢复入口

新对话应先读：

- `plan/state.yaml`

然后按其中的 `current_plan.document` 读取：

- `plan/project-guidance.md`
