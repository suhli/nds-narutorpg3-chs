# 完善项目协作说明

## 背景

本计划用于整理仓库内给后续 AI/Claude/Codex 使用的协作约定。项目是 NDS 游戏《火影忍者 RPG3》汉化工程，后续工作会跨越 ROM 解包/打包、字体逆向、文本 dump、模拟器验证和汉化回写，因此需要先把工作节奏、工具约束和计划恢复入口写清楚。

## 必要上下文

- 原版 ROM 位于 `rom/origin.nds`，只能作为原版输入读取，不能覆盖、原地 patch 或作为打包输出。
- 逆向发现写入 `hack/`。
- 计划正文使用 `.md` 组织，放在 `plan/`。
- 当前计划入口使用 `plan/state.yaml`，新对话应先读这个文件，再跳转到当前计划文档。
- 阶段缓存文档放在 `plan/cache/<plan-id>/`。

## 目标

- 在 `CLAUDE.md` 中记录汉化总体节奏。
- 在 `CLAUDE.md` 中记录 Python、ndstool、DeSmuME MCP 等工具约定。
- 将 ndstool ROM 解包/打包流程做成项目 skill。
- 将 DeSmuME HTTP MCP 调试流程做成项目 skill。
- 修正计划管理方式：统一入口为 `plan/state.yaml`，具体计划用 `.md` 写背景和上下文。

## 阶段

### 1. 汉化总体节奏

状态：已完成。

结论：

- 先解决中文字库和字模承载方案。
- 优先尝试绕开全量字库/字模从 VRAM 加载或常驻。
- 再 dump 所有日文语句。
- 最后汉化、校对、编码转换并回写到新 ROM。

### 2. 工具和 skill 约定

状态：已完成。

结论：

- Python 环境已用 `uv venv` 初始化；依赖安装优先使用 `uv add` 或 `uv pip`。
- `tools/ndstool.exe` 用于 ROM 解包和打包，流程写入 `.claude/skills/ndstool-rom-workflow/SKILL.md`。
- `tools/desmume.exe --mcp` 用于启动模拟器和 HTTP MCP，流程写入 `.claude/skills/desmume-mcp-workflow/SKILL.md`。

### 3. 计划入口重构

状态：已完成。

结论：

- 不再为每个计划创建独立 state YAML。
- `plan/state.yaml` 是唯一状态入口。
- 具体计划正文使用 `.md`。
- 当前阶段缓存写入 `plan/cache/project-guidance/plan-state-rework.md`。

## 决策

- `rom/origin.nds` 不能被覆盖或原地 patch。
- 修改后的 ROM 必须输出为新文件。
- 具体计划必须有背景和必要上下文，避免新对话重新搜索。
- `state.yaml` 必须直接指向当前计划文档、当前阶段和阶段缓存文档。

## 产物

- `CLAUDE.md`
- `.claude/skills/ndstool-rom-workflow/SKILL.md`
- `.claude/skills/desmume-mcp-workflow/SKILL.md`
- `.claude/skills/desmume-mcp-workflow/scripts/list_mcp_tools.py`
- `.claude/skills/desmume-mcp-workflow/scripts/call_mcp_tool.py`
- `plan/state.yaml`
- `plan/project-guidance.md`
- `plan/desmume-mcp-skill.md`
- `plan/cache/project-guidance/plan-state-rework.md`

## 后续

后续任何新任务开始前，先读取 `plan/state.yaml`。如果当前计划未完成，继续当前计划；如果已完成，再判断是否需要创建新的 `.md` 计划文档并更新 `state.yaml`。
