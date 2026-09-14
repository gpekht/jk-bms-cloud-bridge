# JK BMS Cloud Bridge

A lightweight Raspberry Pi collector for a JK BMS. Each one-shot run reads a
live status frame over Bluetooth Low Energy and forwards the measurements to:

- **Grafana Cloud Prometheus** for operational dashboards
- **ThingSpeak** for long-term battery history

The deployed system uses a systemd timer, so no permanent Python collector is
needed and the Bluetooth connection is released after every sample.

## Architecture

```text
JK-B2A8S20P BMS
       │ BLE
       ▼
Raspberry Pi ── jk_push.py (one-shot collector)
       │
       ├── Grafana Cloud Prometheus remote write
       └── ThingSpeak battery and cell channels
```

The parser is currently validated with an eight-cell JK-B2A8S20P (HW V11A,
JK02_32S protocol). The status decoder can represent up to 32 enabled cells,
while the ThingSpeak cell uploader intentionally expects exactly eight.

## Repository layout

```text
bms_reader.py                BLE framing and JK status decoding
grafana_uploader.py          Prometheus remote-write serialization/upload
thingspeak_uploader.py       ThingSpeak summary and cell uploads
jk_push.py                   One-shot orchestration and error logging
prometheus.proto             Minimal remote-write protobuf schema
prometheus_pb2.py            Generated Python protobuf module
grafana/jk-bms-dashboard.json
systemd/jk-bms@.service
systemd/jk-bms@.timer
scripts/network-connectivity-watchdog
systemd/network-connectivity-watchdog.service
systemd/network-connectivity-watchdog.timer
```

## Raspberry Pi setup

These steps assume Raspberry Pi OS or another Debian-based system and a clone
at `/home/YOUR_USER/jk-bms`.

```bash
sudo apt update
sudo apt install -y bluetooth bluez libsnappy-dev python3-venv

cd /home/YOUR_USER/jk-bms
python3 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt
```

Identify the BMS address with `bluetoothctl devices`. Create the private
configuration from the example and fill in the values locally:

```bash
cp .env.example .env
chmod 600 .env
```

Required variables:

| Variable | Purpose |
| --- | --- |
| `JK_BMS_MAC` | Bluetooth MAC address of the JK BMS |
| `THINGSPEAK_BATTERY_KEY` | Write key for the battery-summary channel |
| `THINGSPEAK_CELLS_KEY` | Write key for the eight-cell channel |
| `GRAFANA_URL` | Grafana Cloud Prometheus remote-write URL |
| `GRAFANA_USER` | Grafana Cloud metrics instance/user ID |
| `GRAFANA_TOKEN` | Grafana Cloud token with metrics-write permission |

Never commit `.env`. It is ignored by Git; `.env.example` contains names only.

## Run and verify

Run the protocol tests and compile all Python modules:

```bash
venv/bin/python -m unittest discover -s tests -v
venv/bin/python -m compileall -q .
```

Then perform one live collection and upload:

```bash
venv/bin/python jk_push.py
```

Success is intentionally quiet. The command exits `0`; failures are written to
the terminal and to `logs/jk-bms.log`. Exit `1` means the BMS read failed, and
exit `2` means at least one cloud upload failed.

## Install the systemd timer

The included units are templates. The instance name is the Linux user that owns
the clone. For user `gpekht`, install and start them with:

```bash
sudo install -m 0644 systemd/jk-bms@.service /etc/systemd/system/
sudo install -m 0644 systemd/jk-bms@.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now jk-bms@gpekht.timer
```

For a different account, replace `gpekht` in the last command. The templates
expect the repository at `/home/USERNAME/jk-bms`. Check operation with:

```bash
systemctl status jk-bms@USERNAME.timer
journalctl -u jk-bms@USERNAME.service
```

The timer starts 30 seconds after boot and schedules the next run 30 seconds
after the previous one finishes. To change the cadence, edit
`OnUnitInactiveSec` in the timer before installation.

## System network recovery watchdog

An always-on Raspberry Pi can remain associated with a Wi-Fi access point while
its router reboots. Because the Wi-Fi link never drops, DHCP or DNS may not
recover automatically. The included generic system watchdog checks the default
gateway once a minute and waits for three consecutive failures before
reconnecting Wi-Fi.

DNS is checked through the system resolver using both `example.com` and
`iana.org`. If that fails, the watchdog directly queries both Cloudflare DNS
(`1.1.1.1`) and Google Public DNS (`8.8.8.8`) to distinguish a local resolver
failure from a wider network outage. Repeated system-DNS failures restart only
the configured DNS recovery service, which defaults to Tailscale on this Pi.

Install the script as a root-owned executable and enable its timer:

```bash
sudo install -o root -g root -m 0755 \
  scripts/network-connectivity-watchdog \
  /usr/local/sbin/network-connectivity-watchdog
sudo install -o root -g root -m 0644 \
  systemd/network-connectivity-watchdog.service \
  systemd/network-connectivity-watchdog.timer \
  /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now network-connectivity-watchdog.timer
```

The defaults target `wlan0` and recover after three failed checks. Override them
in the root-owned file `/etc/default/network-connectivity-watchdog` if needed:

```text
WATCHDOG_INTERFACE=wlan0
WATCHDOG_DNS_NAMES=example.com,iana.org
WATCHDOG_DNS_SERVERS=1.1.1.1,8.8.8.8
WATCHDOG_DNS_RECOVERY_SERVICE=tailscaled.service
WATCHDOG_FAILURE_THRESHOLD=3
```

Run a non-recovering diagnostic check with:

```bash
sudo /usr/local/sbin/network-connectivity-watchdog --diagnose
```

Review recovery events with:

```bash
journalctl -u network-connectivity-watchdog.service
```

## Grafana dashboard

In Grafana, open **Dashboards → New → Import** and upload
`grafana/jk-bms-dashboard.json`. Select the Grafana Cloud Prometheus datasource
when prompted. The dashboard includes pack voltage/current/power, state of
charge, temperatures, cell voltages and delta, MOSFET states, cycles, and BMS
error status.

## Security notes

- Credentials, the BMS address, virtual environments, logs, and Python caches
  are excluded from version control.
- Keep `.env` readable only by its owner (`chmod 600 .env`).
- Use a Grafana token limited to metrics publishing.
- Review `git status` and the staged diff before every push.
