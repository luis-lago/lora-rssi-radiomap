# LoRa setup and tests

These scripts configure and test the two Waveshare SX1262 915 MHz UART LoRa HATs. Install the only dependency:

```bash
cd turtlebot4_lora_radiomap/lora
python3 -m pip install -r requirements.txt
ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
```

For the common Waveshare board, configuration mode uses M0 low/shorted and M1 high/open. Normal transparent transmit/receive mode uses M0 low/shorted and M1 low/shorted. Check these labels and positions against the manual for your exact board revision.

Put each HAT in configuration mode and run:

```bash
python configure_lora.py --port /dev/ttyUSB0 --role transmitter
python configure_lora.py --port /dev/ttyUSB0 --role receiver
```

Return both HATs to normal mode. Start the receiver test on one computer:

```bash
python receive_test.py --port /dev/ttyUSB0
```

Send a burst from the other:

```bash
python transmit_test.py --port /dev/ttyUSB0 --burst-id 1 --count 15 --rate-hz 5
```

Each radio packet is 58 bytes. The receiver HAT appends one RSSI byte to its UART output; the receiver test converts it with `raw_rssi - 256`.
