#!/usr/bin/env python3
"""Collect LoRa RSSI measurements at manually selected robot positions."""

import csv
import json
import math
import statistics
import struct
import threading
import time
from datetime import datetime
from pathlib import Path

import requests
import serial

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSDurabilityPolicy, QoSReliabilityPolicy, QoSHistoryPolicy

RAW_FIELDS = [
    "session_id",
    "burst_id",
    "packet_index",
    "receive_time",
    "raw_rssi",
    "rssi_dbm",
    "pose_x",
    "pose_y",
    "pose_yaw",
    "transmitter_id",
    "transmitter_x",
    "transmitter_y",
    "transmitter_z",
]

POSITION_FIELDS = [
    "session_id",
    "burst_id",
    "measurement_time",
    "pose_x",
    "pose_y",
    "pose_yaw",
    "linear_velocity",
    "angular_velocity",
    "packets_transmitted",
    "packets_received",
    "packet_delivery_ratio",
    "mean_rssi_dbm",
    "median_rssi_dbm",
    "std_rssi_db",
    "minimum_rssi_dbm",
    "maximum_rssi_dbm",
    "valid_measurement",
    "transmitter_id",
    "transmitter_x",
    "transmitter_y",
    "transmitter_z",
]


class RobotState(Node):
    def __init__(self, pose_topic, odom_topic):
        super().__init__("lora_radiomap_collector")
        self.pose = None
        self.odom = None
        pose_qos = QoSProfile(
            depth=1,
            durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
            reliability=QoSReliabilityPolicy.RELIABLE,
            history=QoSHistoryPolicy.KEEP_LAST,
        )
        self.create_subscription(
            PoseWithCovarianceStamped, pose_topic, self.pose_callback, pose_qos
        )
        self.create_subscription(Odometry, odom_topic, self.odom_callback, 10)

    def pose_callback(self, message):
        self.pose = message

    def odom_callback(self, message):
        self.odom = message


def ask_transmitter_information():
    while True:
        try:
            count = int(input("Number of transmitters: "))
            if count >= 1:
                break
        except ValueError:
            pass
        print("Enter a whole number of at least one.")

    transmitters = {}
    for number in range(1, count + 1):
        while True:
            transmitter_id = input(f"Transmitter {number} ID: ").strip()
            if transmitter_id and transmitter_id not in transmitters:
                break
            print("The transmitter ID must be non-empty and unique.")

        coordinates = {}
        for axis in ("x", "y", "z"):
            while True:
                try:
                    coordinates[axis] = float(
                        input(f"Transmitter {number} {axis} position [m]: ")
                    )
                    break
                except ValueError:
                    print("Enter a valid number.")
        transmitters[transmitter_id] = coordinates
        print()
    return transmitters


def select_active_transmitter(transmitters):
    transmitter_ids = list(transmitters)
    if len(transmitter_ids) == 1:
        selected_id = transmitter_ids[0]
    else:
        print("Available transmitters:")
        for number, transmitter_id in enumerate(transmitter_ids, start=1):
            position = transmitters[transmitter_id]
            print(
                f"{number}. {transmitter_id} — "
                f"({position['x']:.2f}, {position['y']:.2f}, {position['z']:.2f})"
            )
        while True:
            try:
                choice = int(input("Select active transmitter: "))
                if 1 <= choice <= len(transmitter_ids):
                    selected_id = transmitter_ids[choice - 1]
                    break
            except ValueError:
                pass
            print("Select one of the listed transmitter numbers.")

    print(f"Active transmitter: {selected_id}")
    return selected_id


def build_packet(burst_id, packet_index):
    header = struct.pack(">2sIH", b"RM", burst_id, packet_index)
    return header.ljust(58, b"\x00")


def yaw_from_quaternion(orientation):
    sin_yaw = 2.0 * (
        orientation.w * orientation.z + orientation.x * orientation.y
    )
    cos_yaw = 1.0 - 2.0 * (
        orientation.y * orientation.y + orientation.z * orientation.z
    )
    return math.atan2(sin_yaw, cos_yaw)


def send_burst(radio, burst_id, packet_count, packet_rate):
    transmitted = 0
    for packet_index in range(packet_count):
        try:
            radio.write(build_packet(burst_id, packet_index))
            radio.flush()
        except serial.SerialException as error:
            print(f"Transmitter error after {transmitted} packets: {error}")
            break
        transmitted += 1
        print(f"  sent packet {packet_index}")
        time.sleep(1.0 / packet_rate)
    return transmitted


def get_measurements(pi_url, burst_id, packets_transmitted):
    response = requests.get(
        f"{pi_url.rstrip('/')}/measurements",
        params={"burst_id": burst_id},
        timeout=5,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("burst_id") != burst_id:
        raise ValueError("the Pi returned a different burst ID")

    unique = {}
    for record in data.get("measurements", []):
        packet_index = int(record["packet_index"])
        if 0 <= packet_index < packets_transmitted:
            unique[packet_index] = {
                "packet_index": packet_index,
                "receive_time": float(record["receive_time"]),
                "raw_rssi": int(record["raw_rssi"]),
                "rssi_dbm": int(record["rssi_dbm"]),
            }
    return [unique[index] for index in sorted(unique)]


def create_session(config, config_path):
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output_root = Path(config["output_directory"])
    if not output_root.is_absolute():
        output_root = config_path.parent / output_root
    session_directory = output_root / session_id
    session_directory.mkdir(parents=True, exist_ok=False)

    raw_path = session_directory / "raw_packets.csv"
    position_path = session_directory / "position_measurements.csv"
    with raw_path.open("w", newline="", encoding="utf-8") as output:
        csv.DictWriter(output, fieldnames=RAW_FIELDS).writeheader()
    with position_path.open("w", newline="", encoding="utf-8") as output:
        csv.DictWriter(output, fieldnames=POSITION_FIELDS).writeheader()
    return session_id, session_directory, raw_path, position_path


def save_measurement(
    session_id,
    raw_path,
    position_path,
    burst_id,
    measurement_time,
    robot,
    packets_transmitted,
    packets,
    minimum_received,
    transmitter_id,
    transmitter,
):
    with raw_path.open("a", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=RAW_FIELDS)
        for packet in packets:
            writer.writerow(
                {
                    "session_id": session_id,
                    "burst_id": burst_id,
                    **packet,
                    "pose_x": robot["x"],
                    "pose_y": robot["y"],
                    "pose_yaw": robot["yaw"],
                    "transmitter_id": transmitter_id,
                    "transmitter_x": transmitter["x"],
                    "transmitter_y": transmitter["y"],
                    "transmitter_z": transmitter["z"],
                }
            )

    rssi_values = [packet["rssi_dbm"] for packet in packets]
    received = len(rssi_values)
    row = {
        "session_id": session_id,
        "burst_id": burst_id,
        "measurement_time": measurement_time,
        "pose_x": robot["x"],
        "pose_y": robot["y"],
        "pose_yaw": robot["yaw"],
        "linear_velocity": robot["linear_velocity"],
        "angular_velocity": robot["angular_velocity"],
        "packets_transmitted": packets_transmitted,
        "packets_received": received,
        "packet_delivery_ratio": received / packets_transmitted
        if packets_transmitted
        else 0.0,
        "mean_rssi_dbm": statistics.mean(rssi_values) if rssi_values else "",
        "median_rssi_dbm": statistics.median(rssi_values) if rssi_values else "",
        "std_rssi_db": statistics.pstdev(rssi_values) if rssi_values else "",
        "minimum_rssi_dbm": min(rssi_values) if rssi_values else "",
        "maximum_rssi_dbm": max(rssi_values) if rssi_values else "",
        "valid_measurement": received >= minimum_received,
        "transmitter_id": transmitter_id,
        "transmitter_x": transmitter["x"],
        "transmitter_y": transmitter["y"],
        "transmitter_z": transmitter["z"],
    }
    with position_path.open("a", newline="", encoding="utf-8") as output:
        csv.DictWriter(output, fieldnames=POSITION_FIELDS).writerow(row)


def main():
    config_path = Path(__file__).with_name("config.json")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    session_id, session_directory, raw_path, position_path = create_session(
        config, config_path
    )
    transmitters = ask_transmitter_information()
    transmitter_file = {
        "coordinate_frame": "map",
        "units": "meters",
        "transmitters": [
            {"transmitter_id": transmitter_id, **position}
            for transmitter_id, position in transmitters.items()
        ],
    }
    (session_directory / "transmitters.json").write_text(
        json.dumps(transmitter_file, indent=2) + "\n", encoding="utf-8"
    )
    active_transmitter_id = select_active_transmitter(transmitters)

    rclpy.init()
    node = RobotState(config["pose_topic"], config["odom_topic"])
    spin_thread = threading.Thread(target=rclpy.spin, args=(node,))
    spin_thread.start()
    positions_collected = 0
    used_burst_ids = set()

    try:
        with serial.Serial(
            config["transmitter_serial_port"],
            config["transmitter_baud_rate"],
            write_timeout=1,
        ) as radio:
            print(f"Session data: {session_directory}")
            print("Enter=capture, t=change transmitter, s=status, q=quit")
            while True:
                command = input("radiomap> ").strip().lower()
                if command == "q":
                    break
                if command == "t":
                    active_transmitter_id = select_active_transmitter(transmitters)
                    continue
                if command == "s":
                    print(f"Collected positions: {positions_collected}")
                    position = transmitters[active_transmitter_id]
                    print(f"Active transmitter: {active_transmitter_id}")
                    print(
                        "Position: "
                        f"({position['x']:.2f}, {position['y']:.2f}, "
                        f"{position['z']:.2f}) m"
                    )
                    continue
                if command:
                    print("Use Enter, t, s, or q.")
                    continue
                if node.pose is None or node.odom is None:
                    print(
                        f"Pose received: {node.pose is not None} | "
                        f"Odometry received: {node.odom is not None}"
                    )
                    continue

                pose = node.pose.pose.pose
                twist = node.odom.twist.twist
                robot = {
                    "x": pose.position.x,
                    "y": pose.position.y,
                    "yaw": yaw_from_quaternion(pose.orientation),
                    "linear_velocity": abs(twist.linear.x),
                    "angular_velocity": abs(twist.angular.z),
                }
                if robot["linear_velocity"] > config["maximum_linear_velocity"]:
                    print("Robot is still moving; measurement cancelled.")
                    continue
                if robot["angular_velocity"] > config["maximum_angular_velocity"]:
                    print("Robot is still turning; measurement cancelled.")
                    continue

                measurement_time = time.time()
                measurement_transmitter_id = active_transmitter_id
                measurement_transmitter = transmitters[measurement_transmitter_id]
                burst_id = int(measurement_time) & 0xFFFFFFFF
                while burst_id in used_burst_ids:
                    burst_id = (burst_id + 1) & 0xFFFFFFFF
                used_burst_ids.add(burst_id)

                print(
                    f"Collecting burst {burst_id} at "
                    f"x={robot['x']:.3f}, y={robot['y']:.3f}"
                )
                transmitted = send_burst(
                    radio,
                    burst_id,
                    config["packet_count"],
                    config["packet_rate_hz"],
                )
                time.sleep(config["post_burst_wait_seconds"])

                try:
                    packets = get_measurements(
                        config["receiver_pi_url"], burst_id, transmitted
                    )
                except (requests.RequestException, ValueError, KeyError, TypeError) as error:
                    print(f"Could not retrieve burst {burst_id}: {error}")
                    print(f"Request burst ID {burst_id} from the Pi later. It was not retransmitted.")
                    continue

                save_measurement(
                    session_id,
                    raw_path,
                    position_path,
                    burst_id,
                    measurement_time,
                    robot,
                    transmitted,
                    packets,
                    config["minimum_received_packets"],
                    measurement_transmitter_id,
                    measurement_transmitter,
                )
                positions_collected += 1
                print(
                    f"Measurement complete: {len(packets)}/{transmitted} packets received."
                )
    except (KeyboardInterrupt, EOFError):
        print("\nStopping collection.")
    except serial.SerialException as error:
        print(f"Cannot open transmitter: {error}")
        return 1
    finally:
        rclpy.shutdown()
        spin_thread.join()
        node.destroy_node()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
