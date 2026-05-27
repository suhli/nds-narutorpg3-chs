# 阶段缓存：绕过 VRAM 字体加载计划草案

## 当前阶段

阶段：计划草案。

状态：已完成。

## 缓存上下文

用户要求接下来开始尝试绕过 VRAM 加载，但先做计划。

已有基础：

- `hack/字体加载入口.md` 已记录字体加载核心函数 `FUN_overlay_0__02086870`。
- 已知当前字体 `.chr` 加载到 `0x06880000` 附近 VRAM。
- 已知 `DAT_020B73E0 + 0x24/+0x2C` 保存 1x1/1x2 的 `tbl` 指针。
- 当前主线不是扩大 VRAM 塞完整字库，而是尝试 ROM/RAM 字模主体 + VRAM 当前字形缓存。

## 本阶段处理

- 新增计划正文：`plan/vram-font-bypass.md`。
- 更新统一入口：`plan/state.yaml`。
- 当前计划状态设为 `in_progress`。
- 下一阶段设为 `static-render-chain`，即静态复核字体加载和绘制链路。

## 下一步

先做静态分析，不直接 patch：

- 找到读取 `DAT_020B73E0 + 0x24/+0x2C` 的绘制函数。
- 补写 `hack/字体绘制链路.md`。
- 回写阶段缓存 `plan/cache/vram-font-bypass/static-render-chain.md`。
