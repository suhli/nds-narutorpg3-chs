# 阶段缓存：RAM 预加载容量压力测试

更新时间：2026-05-28

## 目标

验证 `font/chs_probe.bin` 从 NitroFS 预加载到普通 RAM 的容量边界，回答两个问题：

- 字库/字模文件增大后，`0207F80C` 是否还能返回有效 RAM 指针。
- 即使能分配，游戏推进到文本绘制阶段是否仍然稳定。

## 工具

新增脚本：

```text
tools/run_font_preload_size_sweep.py
```

该脚本复用 `tools/patch_vram_font_file_preload_probe.py` 已验证的 hook 布局，只改变 `font/chs_probe.bin` 总大小。文件开头仍保持原 probe 结构，后续用填充字节扩大体积：

```text
u32 entry_count
entry:
  u32 char_code
  u32 glyph_offset
glyph bytes
padding bytes
```

输出 ROM 统一为：

```text
rom/test_vram_font_preload_sweep_<size>.nds
```

## 结果文件

```text
plan/cache/vram-font-bypass/preload-size-sweep.json
plan/cache/vram-font-bypass/preload-size-sweep-boundary.json
plan/cache/vram-font-bypass/preload-size-sweep-boundary2.json
plan/cache/vram-font-bypass/preload-size-sweep-stability.json
plan/cache/vram-font-bypass/preload-size-sweep-960k.json
plan/cache/vram-font-bypass/preload-size-sweep-992k.json
plan/cache/vram-font-bypass/preload-size-sweep-1008k.json

plan/cache/vram-font-bypass/preload-size-512k-samples.json
plan/cache/vram-font-bypass/preload-size-896k-samples.json
plan/cache/vram-font-bypass/preload-size-960k-samples.json
plan/cache/vram-font-bypass/preload-size-992k-samples.json
plan/cache/vram-font-bypass/preload-size-1008k-samples.json
plan/cache/vram-font-bypass/preload-size-1m-samples.json
plan/cache/vram-font-bypass/preload-size-1280k-samples.json
```

## 关键结果

加载层面：

```text
64K    ok, chs_data_ptr=0x02286B60
256K   ok, chs_data_ptr=0x02286B60
512K   ok, chs_data_ptr=0x02286B60
896K   ok, chs_data_ptr=0x02286B60
1008K  ok, chs_data_ptr=0x02286B60
1024K  pointer/size 可写入，但进入文本流程失稳
1376K  可拿到 pointer，但运行状态已出现异常 PC，不可作为稳定容量
1392K  failed, chs_data_ptr=0
1536K  failed, chs_data_ptr=0
2M     failed, chs_data_ptr=0
```

绘制采样层面：

```text
512K:
  0x82CD -> R0=0x02286B80
  0x82DF -> R0=0x02286BC0

896K:
  0x82CD -> R0=0x02286B80
  0x82DF -> R0=0x02286BC0

960K:
  0x82CD -> R0=0x02286B80
  0x82DF -> R0=0x02286BC0

992K:
  0x82CD -> R0=0x02286B80
  0x82DF -> R0=0x02286BC0

1008K:
  0x82CD -> R0=0x02286B80
  0x82DF -> R0=0x02286BC0

1024K:
  未命中 020087BC 正常样本，反复停在异常 PC
```

## 判断

`0207F80C` 对大文件的行为不是“自动分页”，而是尝试为整个文件准备一块连续 RAM：

- 文件过大时，`chs_data_size` 仍可能被写入，但 `chs_data_ptr=0`。
- 接近上限时，即使拿到 pointer，也会挤压后续运行所需 RAM，推进到文本流程后可能失稳。
- 本轮可进入文本绘制并完成两个测试字符采样的最高点是 `1008K`，但它距离 `1024K` 失稳太近。

因此正式方案不应该把完整中文字模作为一个接近 1MB 的常驻文件一次性加载。

## 对正式方案的约束

建议把常驻 RAM 预算分层：

```text
resident map/header: 尽量小，优先常驻
glyph page/chunk: 按场景、文本页或动态需求加载
VRAM glyph cache: 只保留当前画面要绘制的 tile
```

保守设计线：

```text
单个常驻 chs 数据块不要超过 896K。
如果只是临时测试，1008K 可以作为已验证边界样本，但不能作为正式预算。
超过 1MB 的 glyph 数据必须拆页、按需加载或压缩后分段展开。
```

映射表判断：

```text
u32 char_code + u32 glyph_offset = 8 bytes/entry
10000 字 = 约 80KB
20000 字 = 约 160KB
```

映射表本身不太可能先超过 RAM；真正先压垮 RAM 的是 `0x40 bytes/glyph` 的 1x2 glyph 数据。比如 10000 个 1x2 glyph 约 640KB，再加 map 也仍低于本轮保守线；但如果完整覆盖更多字符、同时保留多套字体或未压缩缓存，就会迅速逼近 1MB。

## 下一步

- 正式文件格式应拆成常驻 map/header 与 glyph page/chunk。
- hook 需要处理 `chs_data_ptr=0` 的失败路径，不能假定文件一定加载成功。
- 继续验证 1x1 字体路径，并估算 1x1/1x2 分别需要的 glyph 数量。
