"""
Pure decoder for the Pisonics PS7000 measurement block.

Deliberately has no I/O and no dependencies: hand it a list of raw 16-bit
register values and it hands back named, scaled fields. That keeps the part
you are most likely to get wrong (word order) testable without a device on
the bench -- see test_ps7000.py.

Pisonics -- https://www.pisonics.com
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

_SPEC = Path(__file__).resolve().parents[2] / "registers" / "input-registers.json"

MEASURE_BLOCK_START = 1000

# Two useful read lengths, both inside the 125-register limit of FC 0x04:
#
#   BASE  registers 1000-1086. Present on every firmware from SW 3.3.26.
#   EXT   registers 1000-1113. Adds the entrained-gas index (1104 / 1113),
#         which SW 4.x appends after the base block.
#
# Reading EXT against older firmware returns exception 02 (illegal address).
# Fall back to BASE in that case rather than treating it as a fault -- the
# measurement block is append-only, so BASE always decodes correctly.
MEASURE_BLOCK_LEN_BASE = 87
MEASURE_BLOCK_LEN_EXT = 114
MEASURE_BLOCK_LEN = MEASURE_BLOCK_LEN_BASE   # backwards-compatible default

MAIN_UNITS = {
    0: ("density", "g/cm3"),
    1: ("volume concentration", "%"),
    2: ("mass concentration", "%"),
    3: ("Baume", "degBe"),
    4: ("solids concentration", "g/L"),
    5: ("density", "kg/m3"),
}

MEASURE_ERROR_BITS = {
    0: "NOT_ENOUGH_MEMORY",
    1: "NOT_ENOUGH_DATA",
    2: "SENSOR_TEMPERATURE_INVALID",
    3: "CALIBRATION_DATA_INVALID",
    4: "CALIBRATION_FAILURE",
    5: "FLUCTUATION",
    6: "FAILED",
    7: "SOLUBILITY_CALIBRATION_DATA_INVALID",
}

# Any of these means the published value is STALE -- the firmware returned
# early this cycle and mainValueFiltered still holds the previous frame,
# while the 4-20 mA loop has already dropped to its NAMUR NE43 alarm level.
STALE_BITS = (0, 1, 3, 4, 6)


def _load_spec():
    with open(_SPEC, encoding="utf8") as fh:
        spec = json.load(fh)
    out = {}
    for block in spec["blocks"]:
        for reg in block["registers"]:
            out[reg["reg"]] = reg
    return out


def u16(regs, i):
    return regs[i] & 0xFFFF


def i16(regs, i):
    v = regs[i] & 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def u32(regs, i):
    """CDAB: low word first. This is the single most common integration bug."""
    return (regs[i] & 0xFFFF) | ((regs[i + 1] & 0xFFFF) << 16)


def f32(regs, i):
    return struct.unpack("<f", struct.pack("<I", u32(regs, i)))[0]


_READERS = {"U16": u16, "I16": i16, "U32": u32, "F32": f32}


def decode_block(regs, start=MEASURE_BLOCK_START):
    """Decode a raw register list into a dict of named, scaled values.

    regs   -- list of ints as returned by a Modbus master, index 0 == `start`
    start  -- register number of regs[0]
    """
    spec = _load_spec()
    out = {}
    for reg_no, meta in spec.items():
        idx = reg_no - start
        if idx < 0 or idx >= len(regs):
            continue
        reader = _READERS[meta["type"]]
        if idx + (2 if meta["type"] in ("U32", "F32") else 1) > len(regs):
            continue
        value = reader(regs, idx)
        if "scale" in meta:
            value = value * meta["scale"]
        out[meta["field"]] = value
    return out


def value_is_stale(measure_error_code: int) -> bool:
    """True when the instrument did not produce a new value this cycle.

    Do NOT use the `ok` field for this. `ok` reports sampling quality and is
    routinely 0 on aerated slurry while the reading is perfectly fresh; code
    that treats ok==0 as 'frozen' will silently suppress threshold alarms the
    moment the process gets noisy.
    """
    return any(measure_error_code & (1 << b) for b in STALE_BITS)


def decode_errors(measure_error_code: int):
    return [name for bit, name in MEASURE_ERROR_BITS.items()
            if measure_error_code & (1 << bit)]


def describe(decoded: dict) -> str:
    unit_code = int(decoded.get("mainValueUnit", 0))
    quantity, unit = MAIN_UNITS.get(unit_code, ("value", "?"))
    lines = [
        f"{quantity:>22}: {decoded.get('mainValueFiltered', float('nan')):.4f} {unit}",
        f"{'probe temperature':>22}: {decoded.get('sensorTemperature', float('nan')):.2f} degC"
        + ("" if decoded.get("sensorTemperatureValid") else "   (INVALID)"),
        f"{'signal quality':>22}: {decoded.get('signalQuality', float('nan')):.3f}",
        f"{'loop 1':>22}: {decoded.get('output1Current', float('nan')):.3f} mA",
        f"{'up time':>22}: {int(decoded.get('upTime', 0))} s",
    ]
    if "gasIndexEma" in decoded:
        lines.append(f"{'entrained gas (EMA)':>22}: {int(decoded['gasIndexEma'])} / 100")
    err = int(decoded.get("measureErrorCode", 0))
    if err:
        lines.append(f"{'errors':>22}: {', '.join(decode_errors(err))}")
    if value_is_stale(err):
        lines.append(f"{'!!':>22}: value is STALE, loop is at alarm level")
    return "\n".join(lines)
