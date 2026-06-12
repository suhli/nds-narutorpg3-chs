# NDS Naruto RPG3 Chinese Patch

## 项目简介

这是 NDS 游戏《火影忍者 RPG3》的中文汉化工程。仓库只保存汉化补丁、构建脚本、前端打补丁页面和必要的逆向记录，不发布原版 ROM，也不发布已经打好补丁的 ROM。

使用时需要自行准备合法来源的原版 ROM，然后通过网页或本地脚本应用补丁：

- 在线打补丁页面：[suhli.github.io/nds-narutorpg3-chs/](https://suhli.github.io/nds-narutorpg3-chs/)

## 目录简介

- `patcher/`：最终补丁数据和本地构建 CLI，包括从原版 ROM 生成汉化 ROM、生成 BPS 补丁的脚本。
- `web/`：Vue/Vite 前端页面，用浏览器在本地对用户选择的原版 ROM 应用 BPS 补丁。
- `dist/`：发布用 BPS 补丁文件。
- `hack/`：逆向分析记录、格式说明和关键发现。
- `plan/`：开发过程计划、阶段记录和验证记录。
- `rom/`：本地 ROM 输入输出目录，已被忽略，不应提交。
- `.github/workflows/`：GitHub Pages 构建和发布流程。

## 开发指引

### Codex / Claude 继续开发必备入口

使用 Codex 或 Claude 继续开发时，先让它读取对应入口文件：

- Codex：`AGENTS.md`
- Claude：`CLAUDE.md`

这两个文件记录了项目约束、计划状态、ROM 处理规则、模拟器调试规则和可用 skill。做实质性逆向、ROM 修改或新计划时，需要继续使用里面定义的 `plan-writer` / `plan-reviewer` 流程；只做 README 这类文档小改时可以按当前任务要求跳过计划。

仓库内已经提供的辅助入口：

- `.codex/skills/`、`.claude/skills/`：NDS ROM 解包/回包、DeSmuME MCP 调试流程。
- `.codex/subagents/`、`.claude/agents/`：计划生成和评审代理。
- `hack/`：逆向记录，新发现需要同步补充到这里。
- `plan/`：计划状态和阶段记录，常规开发任务需要先读后写。

### 本地必备工具

继续开发前，本地需要准备这些工具和文件：

- 原版 ROM：放在 `rom/origin.nds`，只作为输入读取，不提交，不覆盖。
- Python / uv / `.venv`：用于运行 patcher、BPS 生成和静态校验；优先使用仓库内 `.venv`。
- Node.js / npm：用于 `web/` 前端开发和构建。
- ndstool：用于 NDS ROM 解包、检查和回包；本地放到 `tools/ndstool.exe`，`tools/` 不提交。
- DeSmuME MCP：只在用户明确要求运行时调试时使用；本地放到 `tools/desmume.exe`，`tools/` 不提交。这个版本是修改过的 fork，可以在 [suhli/desmume](https://github.com/suhli/desmume) 的 GitHub Actions 对应平台 workflow 中，查看 `upload artifact` step 找到下载地址。

默认不要启动 DeSmuME，也不要用 MCP 代替人工运行时验证。未经明确要求时，Codex / Claude 应完成静态字节核对、结构检查、构建和脚本级验证，然后把候选 ROM 或补丁交给人工测试。

### 常用命令

本地构建汉化 ROM：

```powershell
.\.venv\Scripts\python.exe -B patcher\patcher.py --output rom\narutorpg3_chs.nds
```

生成 BPS 补丁：

```powershell
.\.venv\Scripts\python.exe -B patcher\make_bps.py
```

前端开发：

```powershell
cd web
npm install
New-Item -ItemType Directory -Force -Path public
Copy-Item ..\dist\narutorpg3_chs_v36.bps public\narutorpg3_chs_v36.bps -Force
npm run dev
```

发布流程会在打 `v*` 标签时临时把 `dist/narutorpg3_chs_v36.bps` 复制到 `web/public/`，执行 Vite 构建，然后部署到 GitHub Pages。`web/public/` 不提交到仓库。
