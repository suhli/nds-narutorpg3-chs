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

## 后续用户调整

用户要求直接全部写回做成测试成品。已构建：

```text
rom/narutorpg3_chs_full_writeback_test.nds
```

全量写回记录：

```text
plan/cache/text-writeback-smoke/full-writeback-test.md
plan/cache/text-writeback-smoke/full-writeback-records.json
```

下一步 DeSmuME 测试应优先加载全量测试 ROM，而不是旧的样本 ROM。

## 全量 ROM 菜单截图通道校正

更新时间：2026-06-02

现象：

- 用户手动打开的 DeSmuME 窗口已进入红色标题菜单，但 `nds_screenshot` 返回的是另一个蓝色标题画面实例。
- 系统进程检查显示存在多个 DeSmuME 进程；MCP 端口截图与用户可见窗口不同步。

处理：

- 停止使用 MCP 截图作为当前可见窗口依据。
- 改用 Windows 桌面截图并枚举窗口矩形，定位到 DeSmuME 可见窗口：

```text
process_id=37436
window_title=DeSmuME 0.9.14 git#c521618 x64-JIT SSE2 | NARUTO -ナルト-  ナルトRPG3
rect=left 1290 top 190 right 1562 bottom 662
```

截图：

```text
plan/cache/text-writeback-smoke/desktop-screen-test.png
plan/cache/text-writeback-smoke/windows-desmume-menu.png
```

观察：

- `windows-desmume-menu.png` 与用户当前红色标题菜单一致。
- 后续菜单显示/存档入口验证应优先用 Windows 窗口截图记录可见结果；MCP 可继续用于寄存器、内存或输入，但截图结果需要先确认连接的是同一实例。

## 标题菜单文字未变化定位

更新时间：2026-06-02

用户观察：

- 红色标题菜单中 `はじめから`、`ＷｉーＦｉせってい`、`ともだちにくばる` 仍为日文。
- 这不是截图缓存问题，Windows 窗口截图已确认可见画面。

定位结果：

- 这些标题菜单选项没有出现在 `text/writeback/encoded_preview.tsv` 的 overlay 来源中；全量写回记录 `full-writeback-records.json` 中 `overlay_records=0`。
- 当前文本 dump 默认扫描根为：

```text
rom/unpacked/origin/data/text
```

- 标题菜单选项实际位于：

```text
rom/unpacked/origin/overlay/overlay_0004.bin
rom/unpacked/narutorpg3_chs_full_writeback_test/overlay/overlay_0004.bin
```

关键槽位：

```text
0x5270 slot=0x10  　はじめから
0x5280 slot=0x18 　ＷｉーＦｉせってい
0x5298 slot=0x14 　ともだちにくばる
0x52AC slot=0x10 　つづきから
0x52BC slot=0x10 　はじめから
0x52CC slot=0x14 　ファイルさくじょ
0x52E0 slot=0x18 　ＷｉーＦｉせってい
0x52F8 slot=0x14 　ともだちにくばる
```

字体相关观察：

- 全量 ROM 中 `data/font/font_1x1.tbl` 和 `data/font/font_1x2.tbl` 与原版 SHA1 相同。
- 当前字体方案是动态缓存附加文件和 `arm9.bin`/`overlay_0000.bin` patch，不是直接替换原始 `.tbl/.chr` 成完整中文字库。
- 所以菜单日文未变化的直接原因是 overlay 字符串未纳入 dump/写回；是否能显示中文仍需要 overlay 探针 ROM 验证。

已构建探针 ROM：

```text
.\.venv\Scripts\python.exe -B tools\build_title_menu_overlay_probe_rom.py
```

输出：

```text
rom/narutorpg3_chs_full_writeback_menu_overlay_probe.nds
rom/unpacked/narutorpg3_chs_full_writeback_menu_overlay_probe/
plan/cache/text-writeback-smoke/menu-overlay-probe-records.json
```

`ndstool -i` 校验：

```text
Game title=NARUTORPG3
Game code=ANTJ
Header CRC=OK
Banner CRC=OK
ARM9 footer found
```

逆向记录：

```text
hack/标题菜单文本来源.md
```
