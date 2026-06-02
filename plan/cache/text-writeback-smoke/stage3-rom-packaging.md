# Stage 3: 字体资源集成与独立 ROM 打包

更新时间：2026-06-02

## 状态

已完成。

## 输入

```text
rom/unpacked/origin/
plan/cache/text-writeback-smoke/font-build-smoke-sjis-code-table/
plan/cache/text-writeback-smoke/sample-writeback-records.json
```

## 构建命令

```text
.\.venv\Scripts\python.exe -B tools\build_text_writeback_smoke_rom.py
```

## 输出

```text
rom/text_writeback_smoke.nds
rom/unpacked/text_writeback_smoke_build_20260602_180705/
```

`rom/origin.nds` 未修改、未覆盖。

## ndstool 验证

命令：

```text
.\tools\ndstool.exe -i rom\text_writeback_smoke.nds
```

摘要：

```text
Game title=NARUTORPG3
Game code=ANTJ
Header CRC=OK
Banner CRC=OK
ARM9 footer found
```

输出 ROM 可被 ndstool 读取。

## 注意

第一次构建因 source_file 到 ROM data 路径缺少 `text/` 前缀而停止，产生了未使用的工作目录：

```text
rom/unpacked/text_writeback_smoke/
```

实际成功构建使用：

```text
rom/unpacked/text_writeback_smoke_build_20260602_180705/
```
