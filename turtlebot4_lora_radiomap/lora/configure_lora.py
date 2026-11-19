#!/usr/bin/env python3
"""Configure a Waveshare SX1262 915 MHz LoRa HAT."""

import argparse
import time

import serial


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    parser.add_argument("--role", choices=["transmitter", "receiver"], required=True)
    args = parser.parse_args()

    # Registers: address, network ID, 9600/2.4k, 64-byte buffer/13 dBm,
    # channel 65, transparent mode with optional packet RSSI, encryption key.
    reg3 = 0x00 if args.role == "transmitter" else 0x80
    registers = bytes([0x00, 0x00, 0x00, 0x63, 0x82, 65, reg3, 0x00, 0x00])
    read_command = bytes([0xC1, 0x00, 0x09])
    write_command = bytes([0xC0, 0x00, 0x09]) + registers

    try:
        with serial.Serial(args.port, 9600, timeout=1) as radio:
            radio.reset_input_buffer()
            radio.write(read_command)
            time.sleep(0.2)
            current = radio.read(radio.in_waiting or 12)
            print("Current configuration:", current.hex(" "))

            radio.reset_input_buffer()
            radio.write(write_command)
            radio.flush()
            time.sleep(0.2)
            response = radio.read(radio.in_waiting or 12)
            print("Configuration command:", write_command.hex(" "))
            print("Module response:      ", response.hex(" "))

            expected = bytes([0xC1]) + write_command[1:]
            if response == expected:
                print(f"Configuration succeeded for the {args.role}.")
            else:
                print("Configuration failed: unexpected module response.")
                return 1
    except serial.SerialException as error:
        print(f"Serial error: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
