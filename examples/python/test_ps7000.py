"""Round-trip tests for the PS7000 decoder. No instrument required.

Run:  python -m pytest test_ps7000.py -v
 or:  python test_ps7000.py
"""
import struct
import ps7000


def _encode(values):
    """Build a raw register list the way the instrument packs it (CDAB)."""
    regs = [0] * ps7000.MEASURE_BLOCK_LEN_EXT
    spec = ps7000._load_spec()
    by_field = {m["field"]: (r, m) for r, m in spec.items()}
    for field, value in values.items():
        reg_no, meta = by_field[field]
        i = reg_no - ps7000.MEASURE_BLOCK_START
        t = meta["type"]
        if t == "F32":
            bits = struct.unpack("<I", struct.pack("<f", value))[0]
            regs[i] = bits & 0xFFFF
            regs[i + 1] = (bits >> 16) & 0xFFFF
        elif t == "U32":
            regs[i] = value & 0xFFFF
            regs[i + 1] = (value >> 16) & 0xFFFF
        elif t == "I16":
            regs[i] = value & 0xFFFF
        else:
            regs[i] = value & 0xFFFF
    return regs


def test_float_word_order():
    """A float must survive the CDAB round trip. Get this wrong and every
    process value reads as garbage -- it is the failure we most want caught."""
    regs = _encode({"mainValueFiltered": 1.2345})
    got = ps7000.decode_block(regs)["mainValueFiltered"]
    assert abs(got - 1.2345) < 1e-6, got


def test_low_word_really_is_first():
    """Guard against someone 'fixing' the decoder to ABCD."""
    regs = [0] * ps7000.MEASURE_BLOCK_LEN_EXT
    i = 1026 - 1000
    bits = struct.unpack("<I", struct.pack("<f", 1.0))[0]   # 0x3F800000
    regs[i] = bits & 0xFFFF          # 0x0000  low word first
    regs[i + 1] = (bits >> 16) & 0xFFFF   # 0x3F80
    assert abs(ps7000.decode_block(regs)["mainValueFiltered"] - 1.0) < 1e-9


def test_signed_temperature():
    regs = _encode({"mcuTemperature": -125})     # -12.5 degC, scale 0.1
    assert abs(ps7000.decode_block(regs)["mcuTemperature"] + 12.5) < 1e-9


def test_u32_uptime():
    regs = _encode({"upTime": 100_000})
    assert ps7000.decode_block(regs)["upTime"] == 100_000


def test_scaling_applied():
    regs = _encode({"dc": 1234})                 # scale 0.1
    assert abs(ps7000.decode_block(regs)["dc"] - 123.4) < 1e-9


def test_stale_detection():
    assert ps7000.value_is_stale(1 << 6) is True          # FAILED
    assert ps7000.value_is_stale(1 << 3) is True          # CALIBRATION_DATA_INVALID
    assert ps7000.value_is_stale(0) is False


def test_fluctuation_is_not_stale():
    """FLUCTUATION (bit 5) is a quality hint, not a freeze. Treating it as
    stale would suppress alarms on noisy but perfectly live slurry."""
    assert ps7000.value_is_stale(1 << 5) is False


def test_error_names():
    assert ps7000.decode_errors((1 << 0) | (1 << 6)) == [
        "NOT_ENOUGH_MEMORY", "FAILED"]


def test_gas_index_decodes():
    regs = _encode({"gasIndexEma": 37})
    assert ps7000.decode_block(regs)["gasIndexEma"] == 37


def test_base_length_read_omits_gas_without_crashing():
    """A short read against older firmware must degrade cleanly, not raise."""
    regs = _encode({"mainValueFiltered": 1.5})[:ps7000.MEASURE_BLOCK_LEN_BASE]
    out = ps7000.decode_block(regs)
    assert abs(out["mainValueFiltered"] - 1.5) < 1e-6
    assert "gasIndexEma" not in out


def test_no_field_straddles_the_base_boundary():
    """Nothing may start inside the base block and end outside it, or a
    BASE-length read would return a half-decoded value."""
    spec = ps7000._load_spec()
    last = ps7000.MEASURE_BLOCK_START + ps7000.MEASURE_BLOCK_LEN_BASE
    for reg, meta in spec.items():
        width = 2 if meta["type"] in ("U32", "F32") else 1
        if ps7000.MEASURE_BLOCK_START <= reg < last:
            assert reg + width <= last, f"{meta['field']} straddles the boundary"


def test_describe_runs():
    regs = _encode({
        "mainValueFiltered": 1.42, "mainValueUnit": 0,
        "sensorTemperature": 31.5, "sensorTemperatureValid": 1,
        "signalQuality": 0.93, "output1Current": 11.2,
        "upTime": 86400, "gasIndexEma": 4,
    })
    text = ps7000.describe(ps7000.decode_block(regs))
    assert "1.4200 g/cm3" in text and "entrained gas" in text


if __name__ == "__main__":
    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); passed += 1; print(f"  PASS  {name}")
            except AssertionError as e:
                failed += 1; print(f"  FAIL  {name}: {e}")
    print(f"\n{passed} passed, {failed} failed")
    raise SystemExit(1 if failed else 0)
