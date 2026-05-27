# 阶段缓存：静态复核字体加载和绘制链路

## 当前阶段

阶段：静态复核字体加载和绘制链路。

状态：已完成（静态链路完成，部分结论已被运行时观察修正）。

## 目标

- 解包 `rom/origin.nds` 到只读参考工作目录。
- 确认 ARM9、overlay、NitroFS 中字体相关文件和地址。
- 从已知 `FUN_overlay_0__02086870` 反推字体加载链路。
- 找到读取 `DAT_020B73E0 + 0x20/+0x28` 的 tbl 指针，以及 `+0x24/+0x2C` 项计数的绘制/查表函数候选。
- 将结论写入 `hack/字体绘制链路.md`。

## 约束

- 不覆盖 `rom/origin.nds`。
- 本阶段不构建测试 ROM，不 patch ROM。
- 所有 ROM 操作只做解包和静态读取。

## 进行记录

- 已读取 `plan/state.yaml` 和 `plan/vram-font-bypass.md`。
- 已读取 `.codex/skills/ndstool-rom-workflow/SKILL.md`。
- 已解包 `rom/origin.nds` 到 `rom/unpacked/origin/`。
- 已确认 overlay_0000 基址为 `0x0207E320`。
- 已确认字体初始化入口 `02086870`。
- 已确认查表函数：
  - `020866BC`：4 字节表项二分查找。
  - `0208671C`：字符编码和模式到 glyph VRAM 地址。
  - `0208913C` / `0208916C`：调用查表并复制 glyph 数据的绘制路径候选。
- 已写入 `hack/字体绘制链路.md`。

## 关键结论

- `02086870` 通过 `0207F80C` 加载字体资源。
- `0208671C` 按 `mode` 读取 `.tbl` 指针、`.tbl` 项计数、`.chr` 基址和单位大小。
- 返回公式为 `chr_base + unit_size * glyph_index`。
- 静态推断中关于 `.tbl` 驻留 RAM 的判断已被运行时观察修正：`.tbl` 实际也在 VRAM 字体区域。
