# Byte order, word order, and the off-by-one

Three things account for most of the time lost when first connecting to a
PS7000. None of them are exotic; they are just easy to get wrong quietly.

## 1. Register numbers are 1-based, frame addresses are not

Everything in this repository uses **register numbers**, which start at 1.
The address that goes into the Modbus request is **one lower**.

| You want | Put in the frame |
|---|---|
| register 1026 | 1025 (0x0401) |
| register 1000 | 999 (0x03E7) |

Get this wrong and the block still reads successfully — it is simply shifted
by one register, so `mainValueFiltered` returns half of one float and half of
another. The symptom is a plausible-looking but wildly wrong number, which is
worse than an error.

Some masters (and most Python libraries, including pymodbus) expect the raw
frame address. Others, notably a lot of PLC configuration software, expect
the 1-based number and subtract for you. Check which one you have by reading
register 805: it must return 0x50 or 0x51. Any other value means you are off
by one.

## 2. 32-bit values are CDAB

A float or a U32 occupies two consecutive registers. The **low word comes
first**:

```
register n     = bits 15..0    (low)
register n + 1 = bits 31..16   (high)
```

Each register is big-endian internally, per the Modbus specification. In the
vocabulary most masters use, this is **CDAB** — also labelled "word swapped",
"little-endian byte swap", or "Daniel/Enron order" depending on the vendor.

**Most masters default to ABCD.** If your floats come out as denormals,
enormous numbers, or zero, this is why. Set the word order and try again
before suspecting the instrument.

Reference implementation:

```python
def f32(regs, i):
    bits = (regs[i] & 0xFFFF) | ((regs[i + 1] & 0xFFFF) << 16)
    return struct.unpack("<f", struct.pack("<I", bits))[0]
```

A quick sanity check without any tooling: read registers 1026–1027 while the
probe sits in clean water. You should get roughly 1.0, not 4.6e-41.

## 3. Read the block in one request

The measurement block is contiguous and consistent — the firmware publishes a
snapshot, so a single read cannot catch a half-updated frame. Reading fields
one at a time is slower *and* can mix values from different measurement
cycles.

| Read | Registers | Notes |
|---|---|---|
| Base | 1000–1086 (87) | Every firmware from SW 3.3.26 |
| Extended | 1000–1113 (114) | SW 4.x, adds the entrained-gas index |

Function code 0x04 allows 125 registers per request, so both fit in one
transaction. If the extended read returns exception 02, the instrument is
running older firmware: fall back to the base length rather than reporting a
fault. The block is append-only, so the base fields never move.

## 4. Poll rate

Register 1076 (`oneCycleCostTime`) reports how long one measurement cycle
takes, in milliseconds. Polling faster than that returns the same snapshot
repeatedly and buys nothing but bus traffic.
