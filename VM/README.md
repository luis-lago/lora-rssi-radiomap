# Pre-Configured Ubuntu 24.04 (ROS 2 Jazzy) Control VM

This image lets you skip installing Ubuntu 24.04, ROS 2 Jazzy, the TurtleBot4 packages, and the Python dependencies yourself. It is the same control environment used for the measurement sessions in this repository.

## Image Contents

- **Operating system**: Ubuntu 24.04 LTS Desktop (ARM64, for Apple Silicon hosts)
- **ROS**: ROS 2 Jazzy with the TurtleBot4 desktop, navigation, and visualization packages
- **Project files**: `~/Desktop/turtlebot4_lora_radiomap/` and the lab map in `~/Desktop/maps/`
- **Suggested resources**: 2 or more CPUs, at least 4 GB of RAM, and about 20 GB of disk space
- **Tested with**: Parallels Desktop and UTM on Apple Silicon Macs

## Download

The images are too large for the Git repository, so they are provided through [Release v1.0.0](https://github.com/luis-lago/lora-rssi-radiomap/releases/tag/v1.0.0).

| Hypervisor | File | Size (uncompressed) |
| :--- | :--- | :--- |
| Parallels Desktop | `Ubuntu-Linux-24-TBL4-Jazzy.pvm` | About 18 GB |
| UTM / QEMU | `utm-disk.qcow2` | About 16 GB |

If the download comes in split parts (`.zst.part-*`), join and decompress them before use:

```bash
# UTM (.qcow2)
cat utm-disk.qcow2.zst.part-* | zstd -d -o utm-disk.qcow2

# Parallels Desktop (.pvm)
cat Ubuntu-Linux-24-TBL4-Jazzy.pvm.tar.zst.part-* | tar --zstd -xf -
```

## Setup

1. Create a VM from the image in your hypervisor.
2. Connect the host computer to the same Wi-Fi network as the TurtleBot4 and the Raspberry Pi, and set the VM network adapter to **Bridged Mode** so the VM gets an address on that same network.
3. Pass the transmitter LoRa HAT's USB connection through to the VM.

## Check the VM

After logging in, confirm the network, ROS 2, and serial connections:

```bash
ping -c 3 <TURTLEBOT4_IP>
ping -c 3 raspberrypi.local

source /opt/ros/jazzy/setup.bash
ros2 topic list

ls -l /dev/ttyUSB*
```

If the TurtleBot4 uses a Discovery Server, make sure the VM's ROS 2 settings match the robot's IP address, as described in the [Discovery Server guide](https://turtlebot.github.io/turtlebot4-user-manual/setup/discovery_server.html).

When `/dev/ttyUSB0` appears and the ROS 2 topics are listed, continue with [Running Live RSSI Data Collection](../README.md#running-live-rssi-data-collection).
