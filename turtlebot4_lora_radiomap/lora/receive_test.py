#!/usr/bin/env python3
"""Print 58-byte radio-map packets and their appended RSSI byte."""

import argparse
import struct

import serial


def records_from_buffer(buffer):
    while True:
        start = buffer.find(b"RM")
        if start < 0:
            buffer[:] = buffer[-1:] if buffer[-1:] == b"R" else b""
            return
        del buffer[:start]
        if len(buffer) < 59:
            return
        packet = bytes(buffer[:58])
        raw_rssi = buffer[58]
        del buffer[:59]
        burst_id, packet_index = struct.unpack(">IH", packet[2:8])
        yield burst_id, packet_index, raw_rssi


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    args = parser.parse_args()

    buffer = bytearray()
    try:
        with serial.Serial(args.port, 9600, timeout=0.2) as radio:
            while True:
                buffer.extend(radio.read(radio.in_waiting or 59))
                for burst_id, packet_index, raw_rssi in records_from_buffer(buffer):
                    print(
                        f"burst={burst_id} packet={packet_index} "
                        f"rssi={raw_rssi - 256} dBm"
                    )
    except KeyboardInterrupt:
        print("\nReceiver stopped.")
    except serial.SerialException as error:
        print(f"Serial error: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
