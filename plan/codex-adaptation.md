# 适配 Codex 项目入口

## 背景

当前仓库已有 Claude 侧入口 `CLAUDE.md` 和 `.claude/skills/` 项目技能。用户要求复制一份 subagents/skills 和 `CLAUDE.md` 以适配 Codex，目的是让新对话或 Codex 环境可以直接读取 Codex 侧入口，而不用依赖 Claude 命名约定。

## 必要上下文

- 现有 Claude 侧技能目录为 `.claude/skills/`。
- 当前没有发现 `.claude/subagents/` 或 `.claude/agents/` 目录，因此本次只复制现有 skills。
- Codex 项目说明入口使用 `AGENTS.md`。
- Codex 侧项目技能副本放在 `.codex/skills/`。
- 计划入口统一由 `plan/state.yaml` 指向本计划和当前阶段缓存。

## 目标

- 复制 `.claude/skills/` 到 `.codex/skills/`。
- 将技能文档和脚本中的 `.claude/skills` 路径适配为 `.codex/skills`。
- 从 `CLAUDE.md` 生成 Codex 入口 `AGENTS.md`，并将 Claude 侧 skill 路径改为 Codex 侧路径。
- 在 `plan/state.yaml` 中记录当前 plan、阶段和阶段缓存。

## 阶段

### 1. 检查现有结构

状态：已完成。

结论：

- `.claude/skills/` 存在。
- `.claude/subagents/` 和 `.claude/agents/` 不存在。
- 仓库根目录没有现有 `.codex/` 和 `AGENTS.md`。

### 2. 复制并适配 Codex 技能

状态：已完成。

结论：

- 已创建 `.codex/skills/`。
- 已复制现有两个 skill：`ndstool-rom-workflow` 和 `desmume-mcp-workflow`。
- 已将 Codex skill 中的辅助脚本路径改为 `.codex/skills/...`。

### 3. 创建 Codex 说明入口

状态：已完成。

结论：

- 已创建 `AGENTS.md`。
- 内容基于 `CLAUDE.md`，并将项目 skill 路径改为 `.codex/skills/...`。

## 决策

- 不凭空创建 subagents；源目录不存在时只记录这一点。
- Claude 侧文件保留不动，Codex 侧使用副本。
- Codex 入口为 `AGENTS.md`，避免让 Codex 依赖 `CLAUDE.md`。

## 产物

- `AGENTS.md`
- `.codex/skills/ndstool-rom-workflow/SKILL.md`
- `.codex/skills/desmume-mcp-workflow/SKILL.md`
- `.codex/skills/desmume-mcp-workflow/agents/openai.yaml`
- `.codex/skills/desmume-mcp-workflow/scripts/list_mcp_tools.py`
- `.codex/skills/desmume-mcp-workflow/scripts/call_mcp_tool.py`
- `plan/state.yaml`
- `plan/codex-adaptation.md`
- `plan/cache/codex-adaptation/codex-entry-copy.md`

## 后续

后续如果新增 Claude 侧 skill，需要同步考虑是否复制到 `.codex/skills/` 并更新 `AGENTS.md` 中的引用。
