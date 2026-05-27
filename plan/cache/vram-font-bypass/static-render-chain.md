# 阶段缓存：静态复核字体加载和绘制链路

## 当前阶段

阶段：静态复核字体加载和绘制链路。

状态：进行中。

## 目标

- 解包 `rom/origin.nds` 到只读参考工作目录。
- 确认 ARM9、overlay、NitroFS 中字体相关文件和地址。
- 从已知 `FUN_overlay_0__02086870` 反推字体加载链路。
- 找到读取 `DAT_020B73E0 + 0x24/+0x2C` 的绘制/查表函数候选。
- 将结论写入 `hack/字体绘制链路.md`。

## 约束

- 不覆盖 `rom/origin.nds`。
- 本阶段不构建测试 ROM，不 patch ROM。
- 所有 ROM 操作只做解包和静态读取。

## 进行记录

- 已读取 `plan/state.yaml` 和 `plan/vram-font-bypass.md`。
- 已读取 `.codex/skills/ndstool-rom-workflow/SKILL.md`。
- 下一步解包原版 ROM，并分析 ARM9/overlay/font 文件。
