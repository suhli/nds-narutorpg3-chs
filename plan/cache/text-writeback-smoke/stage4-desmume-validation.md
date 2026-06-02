# Stage 4: DeSmuME MCP 显示冒烟

更新时间：2026-06-02

## 状态

进行中。

## 待验证 ROM

```text
rom/text_writeback_smoke.nds
```

## 待验证样本

```text
msg/fld/013.m offset=0xAE -> 「这里是病房，您是来探病的吗？」
param/item_data.dat offset=0x3C60 -> 鸣人卡片
```

## 验证要求

- 加载 `rom/text_writeback_smoke.nds`，不要加载 `rom/origin.nds`。
- 记录进入路径、截图或内存观察摘要。
- 如果中文显示失败，记录失败现象并区分：端序、文本解析、字体缓存、样本不可达或布局问题。
- 新的逆向发现同步写入 `hack/`。

## 本轮记录

启动 MCP：

```text
tools/desmume.exe --mcp
```

加载 ROM：

```text
rom/text_writeback_smoke.nds
```

MCP 返回：

```text
nds_load_rom=OK: loaded
nds_get_rom_info=title=NARUTORPG3 code=ANTJ
nds_get_state=running=1 ARM9_PC=0x0200821C ARM7_PC=0x038042B0
```

截图：

```text
plan/cache/text-writeback-smoke/desmume-initial.bmp
plan/cache/text-writeback-smoke/desmume-initial.png
plan/cache/text-writeback-smoke/desmume-after-start-a.bmp
plan/cache/text-writeback-smoke/desmume-after-start-a.png
plan/cache/text-writeback-smoke/desmume-after-title-inputs.bmp
plan/cache/text-writeback-smoke/desmume-after-title-inputs.png
plan/cache/text-writeback-smoke/desmume-after-wait.bmp
plan/cache/text-writeback-smoke/desmume-after-wait.png
plan/cache/text-writeback-smoke/desmume-after-extra-inputs.bmp
plan/cache/text-writeback-smoke/desmume-after-extra-inputs.png
```

观察：

- 样本 ROM 能通过 MCP 加载。
- 游戏能运行到标题画面。
- 标题后按键推进到浅绿色过渡/等待画面，但本轮没有进入样本文本所在界面。
- 因样本文本未显示，本轮不能确认中文扩展码端序或实际中文字形显示。

对照：

```text
rom/narutorpg3_chs_dynamic_font_v0_validate.nds
plan/cache/text-writeback-smoke/desmume-control-dynamic-font-v0.bmp
plan/cache/text-writeback-smoke/desmume-control-dynamic-font-v0.png
```

对照输入时机不一致，仅保留截图，不作为卡死判定依据。

## 结论

本轮完成“ROM 可加载并到标题”的冒烟，但未完成样本文本显示验证。下一步应选择更容易从标题后进入的样本，或用断点/内存观察确认 `F0 40` 这类扩展码是否进入 `0208913C` 的 `R1/current_char`。
