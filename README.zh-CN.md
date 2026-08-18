# PS7000 超声波密度计 Modbus 寄存器表

[English](README.md) · 中文

**派声 PS7000** 系列超声波浆液密度计的**只读** Modbus RTU 寄存器表，附可直接运行的
Python 与 C# 示例客户端。

寄存器表由单一数据源
（[`registers/input-registers.json`](registers/input-registers.json)）生成，解码逻辑
带单元测试——**最容易搞错的那几处是被测过的，不是假设的。**

- 📋 **[寄存器表](registers/README.md)**
- 🔢 [`input-registers.json`](registers/input-registers.json) · [`.csv`](registers/input-registers.csv) — 机器可读
- ⚠️ **[字序与地址差一](docs/byte-order.md)** — 接线前先看这篇
- 🩺 [状态位与错误码](docs/error-codes.md) — 含"怎么判断读到的值是不是新鲜的"
- 🐍 [Python 示例](examples/python/) · 🔷 [C# 示例](examples/csharp/)

## 第一天最容易踩的三个坑

**1. 表里是 1 基寄存器号，报文里的起始地址要减 1。**

读寄存器 1026，报文里填 1025。搞错了照样能读通，只是整块偏移一位，
给出一个**看起来合理但错误**的数——这才是它难查的原因。

**2. 32 位数据是 CDAB（低字在前）。**

多数 Modbus 主站默认 ABCD。浮点数解出来是 0、是天文数字或者是反常的小数，
基本都是这个原因。把字序设成 `little` / `swapped` / `倒序`。

**3. 整块一次读完，不要逐字段读。**

固件发布的是一致性快照。逐字段读不但慢，还可能把不同测量周期的数据混在一起。

**验证上面两条都设对了**：读寄存器 805，应返回 `0x50`（密度/浓度计）或
`0x51`（光谱浓度计）。返回别的值，说明地址偏了一位。

## 快速开始 — Python

```bash
cd examples/python
pip install -r requirements.txt
python read_ps7000.py --port COM3 --slave 1
```

```
             density: 1.4210 g/cm3
   probe temperature: 31.50 degC
      signal quality: 0.930
              loop 1: 11.203 mA
             up time: 86400 s
 entrained gas (EMA): 4 / 100
```

解码逻辑全在 [`ps7000.py`](examples/python/ps7000.py) 这一个文件里，**零依赖**，
可以直接拷进你自己的工程，其余部分不用管。它的测试不需要接仪表就能跑：

```bash
python test_ps7000.py
```

## 只读一个字段的话，读哪个

`mainValueFiltered` —— **寄存器 1026**，F32 浮点。

**必须同时读 `mainValueUnit`（寄存器 1028）。** 同一台仪表可以被配置成用
g/cm³ 或 kg/m³ 报密度，也可以报质量浓度、体积浓度、波美度或 g/L 固含量。
上位机如果写死了单位，等哪天有人在面板上改了配置，数值会差大约 100 倍。

## 读到的值是不是新鲜的？

用 `measureErrorCode`（寄存器 1004）判断，**不要用 `ok`（寄存器 1029）**。

`ok` 反映的是**本测量周期的采样质量**，不是"值有没有更新"。在含气或湍流的浆液上，
`ok` 经常是 0，而主变量完全是新算出来的，4–20mA 回路也正常。

**把 `ok == 0` 当成"数据冻结"来处理的代码，会在工艺一变噪的时候静默掉阈值告警**——
而工艺变噪恰恰是最需要告警的时候。

具体该看哪几个错误位，见 [docs/error-codes.md](docs/error-codes.md)。

## 含气量指示

SW 4.x 固件在密度值之外还输出含气量指数：

| 寄存器 | 字段 | 用途 |
|---|---|---|
| 1104 | `gasIndex` | 瞬时值，0–100。**单个气泡穿过声束就会让它跳一下**，不适合直接报警 |
| 1113 | `gasIndexEma` | 时间平滑值。**报警用这个**：它忽略孤立气泡，只对持续进气有反应 |

采集程序建议把 1113 和主变量一起入库。含气时段事后是补不回来的，
而在按干料吨结算的项目上，**含气会让产量少报**——这笔账拿不出证据就只能认。

## 范围说明

本仓库只覆盖**只读寄存器**（功能码 0x04），即 PLC、DCS、历史库需要的过程量与诊断量。

配置、标定和控制类写操作在随机的《Modbus 通讯手册》里，不在这里。需要的话联系我们。

寄存器号从 **SW 3.3.26** 起保持稳定。测量块是**只追加**的：新固件在末尾加字段，
不移动已有字段，所以按旧版表写的上位机不用改。

## 重新生成表格

```bash
python tools/gen_tables.py
```

**改 JSON，不要改生成出来的 Markdown 和 CSV。**

## 关于派声

[派声 Pisonics](https://www.pisonics.cn) 做在线密度计和浓度计，用在选矿、电力、
化工和疏浚行业。PS7000 系列用超声法测浆液密度，覆盖 DN50–DN1000，
**不含放射源**，因此不需要辐射安全许可证，也没有退役处置问题。

- 产品页 —— https://www.pisonics.cn/products/PS7000
- 密度计怎么选 —— https://www.pisonics.cn/guides/how-to-choose-density-meter

集成相关问题：info@pisonics.com

## 许可

文档与寄存器数据：[CC BY 4.0](LICENSE-DOCS)。示例代码：[MIT](LICENSE)。

---

本仓库同时发布在
[GitHub](https://github.com/Pisonics/ps7000-modbus) ·
[GitCode](https://gitcode.com/Pisonics/ps7000-modbus) ·
[Gitee](https://gitee.com/Pisonics/ps7000-modbus)

© 西安派声信息科技有限公司
