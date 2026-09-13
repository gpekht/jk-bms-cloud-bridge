import logging
import os
import time

import requests
import snappy

from prometheus_pb2 import WriteRequest

logger = logging.getLogger(__name__)


def add_metric(
    write_request,
    name,
    value,
    timestamp_ms,
    labels=None,
):
    series = write_request.timeseries.add()

    name_label = series.labels.add()
    name_label.name = "__name__"
    name_label.value = name

    if labels:
        for key, label_value in labels.items():
            label = series.labels.add()
            label.name = str(key)
            label.value = str(label_value)

    sample = series.samples.add()
    sample.value = float(value)
    sample.timestamp = timestamp_ms


def push_grafana(values):
    grafana_url = os.getenv("GRAFANA_URL")
    grafana_user = os.getenv("GRAFANA_USER")
    grafana_token = os.getenv("GRAFANA_TOKEN")

    if not grafana_url or not grafana_user or not grafana_token:
        raise RuntimeError(
            "Grafana Cloud credentials are missing from environment"
        )

    timestamp_ms = int(time.time() * 1000)

    write_request = WriteRequest()

    common = {
        "device": "jk_bms",
        "model": "JK-B2A8S20P",
    }

    add_metric(
        write_request,
        "jk_bms_voltage_volts",
        values["voltage"],
        timestamp_ms,
        common,
    )

    add_metric(
        write_request,
        "jk_bms_current_amps",
        values["current"],
        timestamp_ms,
        common,
    )

    add_metric(
        write_request,
        "jk_bms_power_watts",
        values["power"],
        timestamp_ms,
        common,
    )

    add_metric(
        write_request,
        "jk_bms_soc_percent",
        values["soc"],
        timestamp_ms,
        common,
    )

    add_metric(
        write_request,
        "jk_bms_soh_percent",
        values["soh"],
        timestamp_ms,
        common,
    )

    add_metric(
        write_request,
        "jk_bms_remaining_capacity_ah",
        values["remaining_ah"],
        timestamp_ms,
        common,
    )

    add_metric(
        write_request,
        "jk_bms_nominal_capacity_ah",
        values["nominal_ah"],
        timestamp_ms,
        common,
    )

    add_metric(
        write_request,
        "jk_bms_cell_delta_mv",
        values["cell_delta_mv"] or 0,
        timestamp_ms,
        common,
    )

    add_metric(
        write_request,
        "jk_bms_balancing_current_amps",
        values["balancing_current"],
        timestamp_ms,
        common,
    )

    add_metric(
        write_request,
        "jk_bms_charge_enabled",
        int(values["charge_enabled"]),
        timestamp_ms,
        common,
    )

    add_metric(
        write_request,
        "jk_bms_discharge_enabled",
        int(values["discharge_enabled"]),
        timestamp_ms,
        common,
    )

    add_metric(
        write_request,
        "jk_bms_balancing_active",
        int(values["balancing_active"]),
        timestamp_ms,
        common,
    )

    add_metric(
        write_request,
        "jk_bms_cycles_total",
        values["cycles"],
        timestamp_ms,
        common,
    )

    add_metric(
        write_request,
        "jk_bms_total_cycle_ah",
        values["total_cycle_ah"],
        timestamp_ms,
        common,
    )

    add_metric(
        write_request,
        "jk_bms_error_mask",
        values["error_mask"],
        timestamp_ms,
        common,
    )

    for sensor_name, temperature in (
        ("battery_1", values["temp1"]),
        ("battery_2", values["temp2"]),
        ("mosfet", values["mosfet_temp"]),
    ):
        add_metric(
            write_request,
            "jk_bms_temperature_celsius",
            temperature,
            timestamp_ms,
            {
                **common,
                "sensor": sensor_name,
            },
        )

    for cell_number, voltage in enumerate(
        values["cells"],
        start=1,
    ):
        add_metric(
            write_request,
            "jk_bms_cell_voltage_volts",
            voltage,
            timestamp_ms,
            {
                **common,
                "cell": str(cell_number),
            },
        )

    raw = write_request.SerializeToString()
    compressed = snappy.compress(raw)

    headers = {
        "Content-Encoding": "snappy",
        "Content-Type": "application/x-protobuf",
        "X-Prometheus-Remote-Write-Version": "0.1.0",
        "User-Agent": "jk-bms-pi/1.0",
    }

    logger.info(
        "Uploading %d metric series to Grafana Cloud",
        len(write_request.timeseries),
    )

    try:
        response = requests.post(
            grafana_url,
            data=compressed,
            headers=headers,
            auth=(grafana_user, grafana_token),
            timeout=15,
        )

    except Exception:
        logger.exception("Grafana Cloud request failed")
        raise

    if response.status_code not in (200, 204):
        logger.error(
            "Grafana upload failed: HTTP %s: %s",
            response.status_code,
            response.text[:500],
        )

        raise RuntimeError(
            f"Grafana upload failed: "
            f"HTTP {response.status_code}"
        )

    logger.info(
        "Grafana Cloud upload OK: HTTP %s",
        response.status_code,
    )

    return response.status_code

