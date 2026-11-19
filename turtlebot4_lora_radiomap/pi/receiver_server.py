#!/usr/bin/env python3
"""Receive LoRa RSSI records, save them, and serve them over HTTP."""

import csv
import json
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import serial


measurements = {}
seen_packets = set()
data_lock = threading.Lock()
stop_event = threading.Event()
serial_connected = False


def records_from_buffer(buffer):
    """Extract complete 58-byte packets plus one appended RSSI byte."""
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


def serial_reader(config, csv_path):
    global serial_connected

    new_file = not csv_path.exists() or csv_path.stat().st_size == 0
    try:
        with csv_path.open("a", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file)
            if new_file:
                writer.writerow(
                    ["burst_id", "packet_index", "receive_time", "raw_rssi", "rssi_dbm"]
                )
                csv_file.flush()

            with serial.Serial(
                config["serial_port"], config["baud_rate"], timeout=0.2
            ) as radio:
                serial_connected = True
                buffer = bytearray()
                print(f"Reading receiver on {config['serial_port']}")
                while not stop_event.is_set():
                    buffer.extend(radio.read(radio.in_waiting or 59))
                    for burst_id, packet_index, raw_rssi in records_from_buffer(buffer):
                        packet_id = (burst_id, packet_index)
                        receive_time = time.time()
                        rssi_dbm = raw_rssi - 256
                        with data_lock:
                            if packet_id in seen_packets:
                                continue
                            seen_packets.add(packet_id)
                            record = {
                                "packet_index": packet_index,
                                "receive_time": receive_time,
                                "raw_rssi": raw_rssi,
                                "rssi_dbm": rssi_dbm,
                            }
                            measurements.setdefault(burst_id, []).append(record)
                            writer.writerow(
                                [burst_id, packet_index, receive_time, raw_rssi, rssi_dbm]
                            )
                            csv_file.flush()
                        print(
                            f"saved burst={burst_id} packet={packet_index} "
                            f"rssi={rssi_dbm} dBm"
                        )
    except (OSError, serial.SerialException) as error:
        print(f"Receiver error: {error}")
    finally:
        serial_connected = False


class RequestHandler(BaseHTTPRequestHandler):
    def send_json(self, status, value):
        body = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path)
        if path.path == "/health":
            with data_lock:
                packet_count = len(seen_packets)
            self.send_json(
                200,
                {
                    "status": "ok",
                    "serial_connected": serial_connected,
                    "packets_received": packet_count,
                },
            )
            return

        if path.path == "/measurements":
            try:
                burst_id = int(parse_qs(path.query)["burst_id"][0])
            except (KeyError, IndexError, ValueError):
                self.send_json(400, {"error": "a numeric burst_id is required"})
                return
            with data_lock:
                result = sorted(
                    (dict(item) for item in measurements.get(burst_id, [])),
                    key=lambda item: item["packet_index"],
                )
            self.send_json(200, {"burst_id": burst_id, "measurements": result})
            return

        self.send_json(404, {"error": "not found"})

    def log_message(self, format_string, *args):
        return


def main():
    config_path = Path(__file__).with_name("config.json")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    csv_path = Path(config["output_csv"])
    if not csv_path.is_absolute():
        csv_path = config_path.parent / csv_path

    server = ThreadingHTTPServer(
        (config["http_host"], config["http_port"]), RequestHandler
    )
    thread = threading.Thread(target=serial_reader, args=(config, csv_path))
    thread.start()
    print(f"HTTP server listening on {config['http_host']}:{config['http_port']}")
    print(f"Saving packets to {csv_path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping receiver server.")
    finally:
        server.server_close()
        stop_event.set()
        thread.join()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
