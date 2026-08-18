# PS7000 Modbus register map

English · [中文](README.zh-CN.md)

Read-only Modbus RTU register map and working example clients for the
**Pisonics PS7000** ultrasonic slurry density meter — a non-nuclear inline
density meter that measures acoustic impedance, so it needs no radioactive
source, no licence and no disposal route.

Everything here is generated from a single source of truth
([`registers/input-registers.json`](registers/input-registers.json)) and the
decoder is unit tested, so the parts that are easy to get wrong are checked
rather than assumed.

- 📋 **[Register map](registers/README.md)** — the tables
- 🔢 [`input-registers.json`](registers/input-registers.json) · [`.csv`](registers/input-registers.csv) — machine readable
- ⚠️ **[Byte order and the off-by-one](docs/byte-order.md)** — read this first
- 🩺 [Status and error codes](docs/error-codes.md) — including how to tell a stale reading
- 🐍 [Python example](examples/python/) · 🔷 [C# example](examples/csharp/)

## Three things that account for most first-day problems

**1. Register numbers here are 1-based; the frame address is one lower.**
To read register 1026, put 1025 in the request. Get it wrong and the block
still reads — just shifted by one, giving a plausible but wrong number.

**2. 32-bit values are CDAB — low word first.** Most masters default to ABCD.
If floats decode as denormals or zeros, this is why.

**3. Read the block in one request.** The firmware publishes a consistent
snapshot; field-by-field reads are slower and can mix measurement cycles.

Quick check that you have both right: read register 805. It must return
`0x50` (density / concentration meter) or `0x51` (spectral concentration
meter). Anything else means you are off by one.

## Quick start — Python

```bash
cd examples/python
pip install -r requirements.txt
python read_ps7000.py --port /dev/ttyUSB0 --slave 1
```

```
             density: 1.4210 g/cm3
   probe temperature: 31.50 degC
      signal quality: 0.930
              loop 1: 11.203 mA
             up time: 86400 s
 entrained gas (EMA): 4 / 100
```

The decoding lives in [`ps7000.py`](examples/python/ps7000.py), which has no
dependencies at all. You can lift that one file into your own project and
ignore the rest. Its tests run without an instrument:

```bash
python test_ps7000.py
```

## The one field to read

`mainValueFiltered` — **register 1026**, F32. Read `mainValueUnit`
(register 1028) alongside it, because the same instrument can be configured to
report density in g/cm³ or kg/m³, mass or volume concentration, Baumé, or
solids in g/L. A host that assumes one will be wrong by roughly 100× the day
someone changes it on the panel.

## Is the reading fresh?

Use `measureErrorCode` (register 1004), **not** the `ok` field (register 1029).

`ok` reports sampling quality for the cycle. On aerated or turbulent slurry it
is routinely 0 while the value is perfectly live and the current loop is
normal. Code that treats `ok == 0` as "frozen" stops acting on alarms exactly
when the process gets noisy. Details and the exact bit list are in
[docs/error-codes.md](docs/error-codes.md).

## Entrained gas

On SW 4.x the instrument reports an entrained-gas index (registers 1104 and
1113) alongside the density value. It is derived from frame-to-frame variance
rather than absolute echo amplitude — which is the point, because amplitude
alone cannot separate "more bubbles" from "more solids": both push it the same
way. Alarm on the smoothed value (1113); the instantaneous one (1104) spikes
on a single bubble crossing the beam.

## Scope

This repository covers **read-only registers** — function code 0x04, the
process values and diagnostics a PLC, DCS or historian needs.

Configuration, calibration and control writes are covered by the official
Modbus manual supplied with the instrument. If you need it, ask us.

Register numbers are stable from **SW 3.3.26** onward. The measurement block
is append-only: newer firmware adds fields at the end and never moves an
existing one, so a host written against an older map keeps working.

## Regenerating the tables

```bash
python tools/gen_tables.py
```

Edit the JSON, never the generated Markdown or CSV.

## About Pisonics

[Pisonics](https://www.pisonics.com) builds inline density and concentration
meters for mining, power generation, chemical processing and dredging. The
PS7000 series measures slurry density by acoustic impedance, covering DN50 to
DN1000 without a radioactive source.

- Product page — https://www.pisonics.com/products/PS7000
- How acoustic impedance measurement works — https://www.pisonics.com/guides/acoustic-impedance-explained
- Choosing a density meter — https://www.pisonics.com/guides/how-to-choose-density-meter

Questions about integration: info@pisonics.com

## Licence

Documentation and register data: [CC BY 4.0](LICENSE-DOCS).
Example code: [MIT](LICENSE).
