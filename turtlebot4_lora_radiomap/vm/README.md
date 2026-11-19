# ROS 2 VM collector

This directory runs in the Ubuntu ROS 2 VM. Pass the transmitter HAT's USB device through to the VM, attach its antenna, and find its serial port:

```bash
ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
```

Source ROS 2 and install the two non-ROS dependencies. The ROS packages `rclpy`, `geometry_msgs`, and `nav_msgs` normally come from the ROS installation.

```bash
source /opt/ros/jazzy/setup.bash
cd turtlebot4_lora_radiomap/vm
python3 -m pip install -r requirements.txt
```

Configure the HAT as the transmitter, then return it to normal mode:

```bash
cd ../lora
python configure_lora.py --port /dev/ttyUSB0 --role transmitter
cd ../vm
```

Check the robot topics and Pi connection:

```bash
ros2 topic echo /amcl_pose --once
ros2 topic echo /odom --once
curl http://192.168.1.50:8080/health
```

Edit `config.json` for the serial port and Pi IP, then start:

```bash
python collect_radiomap.py
```

Manually move and stop the TurtleBot4, then press Enter for each position. Use `s` to show the number collected and `q` to quit. Each run writes `raw_packets.csv` and `position_measurements.csv` under `data/<session_id>/` next to `config.json`.
