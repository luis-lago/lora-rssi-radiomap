# Raspberry Pi receiver

This directory runs on the Raspberry Pi mounted on the TurtleBot4. It reads the receiver HAT continuously, saves every unique packet to CSV, and serves measurements to the VM.

Install Python and `pyserial`:

```bash
cd turtlebot4_lora_radiomap/pi
python3 -m pip install -r requirements.txt
ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
```

Configure the HAT as the receiver, then return its jumpers to normal mode:

```bash
cd ../lora
python configure_lora.py --port /dev/ttyUSB0 --role receiver
cd ../pi
```

Edit `config.json` if the serial device differs, then start the service:

```bash
python receiver_server.py
```

Test it from the VM:

```bash
curl http://192.168.1.50:8080/health
curl "http://192.168.1.50:8080/measurements?burst_id=12"
```

Packets are appended to `receiver_packets.csv` next to `config.json` by default. Give the Pi a stable address using a router DHCP reservation or your operating system's static-network configuration, and put that address in the VM configuration.
