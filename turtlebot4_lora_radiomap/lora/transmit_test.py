#!/usr/bin/env python3
"""Send a short burst of 58-byte radio-map packets."""

import argparse
import struct
import time

import serial


def build_packet(burst_id, packet_index):
    header = struct.pack(">2sIH", b"RM", burst_id, packet_index)
    return header.ljust(58, b"\x00")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    parser.add_argument("--burst-id", type=int, required=True)
    parser.add_argument("--count", type=int, default=15)
    parser.add_argument("--rate-hz", type=float, default=5.0)
    args = parser.parse_args()

    if not 0 <= args.burst_id <= 0xFFFFFFFF:
        parser.error("--burst-id must fit in an unsigned 32-bit integer")
    if not 0 <= args.count <= 65536:
        parser.error("--count must be between 0 and 65536")
    if args.rate_hz <= 0:
        parser.error("--rate-hz must be positive")

    try:
        with serial.Serial(args.port, 9600, write_timeout=1) as radio:
            for packet_index in range(args.count):
                radio.write(build_packet(args.burst_id, packet_index))
                radio.flush()
                print(f"burst={args.burst_id} packet={packet_index}")
                time.sleep(1.0 / args.rate_hz)
    except KeyboardInterrupt:
        print("\nTransmission stopped.")
    except serial.SerialException as error:
        print(f"Serial error: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
