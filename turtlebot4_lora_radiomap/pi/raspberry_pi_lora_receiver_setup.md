# Raspberry Pi Setup Guide — LoRa RSSI Receiver

## 1. Physical connection
- Small USB end → LoRa HAT USB-to-UART port
- USB-A end → Raspberry Pi USB-A host port
- Connect the antenna
- Do not use the Pi USB-C power port for the HAT data cable

## 2. UART selector
Set the LoRa HAT UART selector to `A` for USB-to-UART operation.

## 3. Configuration mode
Before configuring the receiver HAT:
- M0 = SHORTED
- M1 = OPEN

## 4. Detect the HAT on the Pi
```bash
cat /proc/device-tree/model
lsusb
ls -l /dev/ttyUSB*
```

The HAT will typically appear as `/dev/ttyUSB0`.

## 5. Confirm the serial device
Unplug/replug the HAT and confirm which `/dev/ttyUSB*` entry disappears and reappears.

## 6. Install pyserial
```bash
python3 -c "import serial; print(serial.__version__)"
sudo apt update
sudo apt install python3-serial
```

## 7. Serial permissions
```bash
ls -l /dev/ttyUSB0
groups
sudo usermod -aG dialout $USER
```
Log out/in or reboot if `dialout` was newly added.

## 8. Project layout
```text
~/turtlebot4_lora_radiomap/
├── lora/
│   ├── configure_lora.py
│   └── receive_test.py
└── pi/
    ├── receiver_server.py
    ├── config.json
    └── receiver_packets.csv
```

## 9. Configure the HAT as receiver
Verify:
- UART selector = A
- M0 = SHORTED
- M1 = OPEN

Then run:
```bash
cd ~/turtlebot4_lora_radiomap/lora
python3 configure_lora.py --port /dev/ttyUSB0 --role receiver
```

The receiver must use matching RF settings with the transmitter and enable packet-RSSI output.

## 10. Return to normal mode
After configuration:
- M0 = SHORTED
- M1 = SHORTED

Final receiver state:
- UART selector = A
- M0 = SHORTED
- M1 = SHORTED
- Antenna connected
- USB connected to Pi

## 11. Verify serial device
```bash
ls -l /dev/ttyUSB0
lsusb
```

## 12. Test direct reception first
```bash
cd ~/turtlebot4_lora_radiomap/lora
python3 receive_test.py --port /dev/ttyUSB0
```

## 13. Send a small test from the VM
Ensure the transmitter HAT is in normal mode:
- UART selector = A
- M0 = SHORTED
- M1 = SHORTED

Then:
```bash
python3 transmit_test.py   --port /dev/ttyUSB0   --burst-id 1   --count 5   --rate-hz 1
```

Expected receiver output resembles:
```text
burst=1 packet=0 rssi=-42 dBm
burst=1 packet=1 rssi=-43 dBm
...
```

Do not proceed to HTTP until direct LoRa reception works.

## 14. Configure the Pi receiver server
Example `config.json`:
```json
{
  "serial_port": "/dev/ttyUSB0",
  "baud_rate": 9600,
  "http_host": "0.0.0.0",
  "http_port": 8080,
  "output_csv": "receiver_packets.csv"
}
```

## 15. Start the receiver server
```bash
cd ~/turtlebot4_lora_radiomap/pi
python3 receiver_server.py
```

## 16. Test health locally
```bash
curl http://localhost:8080/health
```

Expected structure:
```json
{
  "status": "ok",
  "serial_connected": true,
  "packets_received": 0
}
```

## 17. Find Pi IP address
```bash
hostname -I
```

## 18. Test from the Ubuntu VM
```bash
ping <PI_IP>
curl http://<PI_IP>:8080/health
```

## 19. End-to-end burst test
Keep the Pi server running, then from the VM:
```bash
python3 transmit_test.py   --port /dev/ttyUSB0   --burst-id 100   --count 5   --rate-hz 1
```

Retrieve:
```bash
curl "http://<PI_IP>:8080/measurements?burst_id=100"
```

Check local backup:
```bash
cat receiver_packets.csv
```

## Jumper rule to remember

Configuration mode:
- M0 = SHORTED
- M1 = OPEN

Normal RSSI collection:
- M0 = SHORTED
- M1 = SHORTED
