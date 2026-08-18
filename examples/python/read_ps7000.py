#!/usr/bin/env python3
"""Read a PS7000 over Modbus RTU and print the process values.

    pip install pymodbus pyserial
    python read_ps7000.py --port /dev/ttyUSB0 --slave 1

The decoding lives in ps7000.py, which has no dependencies and is unit
tested -- see test_ps7000.py. This file is only the serial plumbing.

Pisonics -- https://www.pisonics.com
"""
import argparse
import sys
import time

import ps7000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True, help="e.g. /dev/ttyUSB0 or COM3")
    ap.add_argument("--slave", type=int, default=1, help="slave address, default 1")
    ap.add_argument("--baud", type=int, default=9600,
                    choices=[9600, 19200, 38400, 57600, 115200])
    ap.add_argument("--interval", type=float, default=2.0, help="seconds between polls")
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()

    try:
        from pymodbus.client import ModbusSerialClient
    except ImportError:
        sys.exit("pip install pymodbus pyserial")

    client = ModbusSerialClient(port=args.port, baudrate=args.baud,
                                bytesize=8, parity="N", stopbits=1, timeout=1)
    if not client.connect():
        sys.exit(f"cannot open {args.port}")

    # NOTE THE MINUS ONE. Register numbers in the documentation are 1-based;
    # the address that goes in the frame is one lower. Reading 1000 instead
    # of 999 shifts every field by one register and is the classic first-day
    # integration bug.
    address = ps7000.MEASURE_BLOCK_START - 1
    count = ps7000.MEASURE_BLOCK_LEN_EXT

    try:
        while True:
            rr = client.read_input_registers(address=address, count=count,
                                             slave=args.slave)
            if rr.isError():
                # Older firmware has no gas-index registers and answers
                # exception 02 for the longer read. Drop back rather than
                # reporting a fault.
                if count == ps7000.MEASURE_BLOCK_LEN_EXT:
                    count = ps7000.MEASURE_BLOCK_LEN_BASE
                    print("long read refused, falling back to the base block")
                    continue
                print(f"read error: {rr}")
            else:
                print(ps7000.describe(ps7000.decode_block(rr.registers)))
                print("-" * 46)
            if args.once:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        client.close()


if __name__ == "__main__":
    main()
