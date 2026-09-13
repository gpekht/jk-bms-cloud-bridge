import asyncio
import logging
import os
import struct

from bleak import BleakClient

logger = logging.getLogger(__name__)

CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"


def u16(data, offset):
    return struct.unpack_from("<H", data, offset)[0]


def i16(data, offset):
    return struct.unpack_from("<h", data, offset)[0]


def u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def i32(data, offset):
    return struct.unpack_from("<i", data, offset)[0]


def make_command(command, counter=0):
    frame = bytearray(20)

    frame[0:4] = b"\xAA\x55\x90\xEB"
    frame[4] = command
    frame[5] = 0
    frame[16] = counter

    frame[19] = sum(frame[:19]) & 0xFF
    return bytes(frame)


def decode_status(data):
    if len(data) < 300:
        raise ValueError(f"Status frame too short: {len(data)} bytes")

    enabled_cells = u32(data, 70)

    cells = []

    for i in range(32):
        if enabled_cells & (1 << i):
            cells.append(
                u16(data, 6 + i * 2) / 1000.0
            )

    voltage = u32(data, 150) / 1000.0
    current = i32(data, 158) / 1000.0
    power = voltage * current

    mosfet_temp = i16(data, 144) / 10.0
    temp1 = i16(data, 162) / 10.0
    temp2 = i16(data, 164) / 10.0

    error_mask = u32(data, 166)

    balancing_current = i16(data, 170) / 1000.0
    balancing_action = data[172]

    soc = data[173]
    remaining_ah = u32(data, 174) / 1000.0
    nominal_ah = u32(data, 178) / 1000.0

    cycles = u32(data, 182)
    total_cycle_ah = u32(data, 186) / 1000.0
    soh = data[190]

    runtime_seconds = u32(data, 194)

    charge_enabled = bool(data[198])
    discharge_enabled = bool(data[199])
    balancing_active = bool(data[201])

    cell_min = min(cells) if cells else None
    cell_max = max(cells) if cells else None

    cell_delta_mv = (
        (cell_max - cell_min) * 1000.0
        if cells
        else None
    )

    return {
        "voltage": voltage,
        "current": current,
        "power": power,
        "soc": soc,
        "soh": soh,
        "remaining_ah": remaining_ah,
        "nominal_ah": nominal_ah,
        "temp1": temp1,
        "temp2": temp2,
        "mosfet_temp": mosfet_temp,
        "cells": cells,
        "cell_min": cell_min,
        "cell_max": cell_max,
        "cell_delta_mv": cell_delta_mv,
        "balancing_current": balancing_current,
        "balancing_action": balancing_action,
        "balancing_active": balancing_active,
        "charge_enabled": charge_enabled,
        "discharge_enabled": discharge_enabled,
        "cycles": cycles,
        "total_cycle_ah": total_cycle_ah,
        "runtime_seconds": runtime_seconds,
        "error_mask": error_mask,
    }


async def read_bms():
    mac = os.getenv("JK_BMS_MAC")
    if not mac:
        raise RuntimeError("JK_BMS_MAC is missing from environment")

    rx = bytearray()
    status_frame = None
    status_event = asyncio.Event()

    def notification_handler(sender, data):
        nonlocal rx, status_frame

        if len(data) >= 4 and data[:4] == b"\x55\xAA\xEB\x90":
            rx = bytearray()

        rx.extend(data)

        while len(rx) >= 300:
            frame = bytes(rx[:300])
            rx = rx[300:]

            frame_type = frame[4]

            if frame_type == 0x02:
                logger.debug("Received JK live status frame")
                status_frame = frame
                status_event.set()

    logger.info("Connecting to JK BMS")

    try:
        async with BleakClient(mac, timeout=20) as client:
            logger.info("Connected to JK BMS")

            await client.start_notify(
                CHAR_UUID,
                notification_handler
            )

            await client.write_gatt_char(
                CHAR_UUID,
                make_command(0x96, 0),
                response=False
            )

            await asyncio.sleep(1)

            await client.write_gatt_char(
                CHAR_UUID,
                make_command(0x97, 1),
                response=False
            )

            await asyncio.wait_for(
                status_event.wait(),
                timeout=20
            )

            await client.stop_notify(CHAR_UUID)

    except asyncio.TimeoutError as exc:
        logger.error("Timed out waiting for JK BMS status frame")
        raise RuntimeError(
            "Timed out waiting for JK BMS status frame"
        ) from exc

    except Exception:
        logger.exception("BLE communication with JK BMS failed")
        raise

    if status_frame is None:
        raise RuntimeError("JK BMS returned no status frame")

    values = decode_status(status_frame)

    logger.info(
        "BMS read OK: %.3f V, %+.2f A, %.0f%% SOC, %.0f mV delta",
        values["voltage"],
        values["current"],
        values["soc"],
        values["cell_delta_mv"] or 0,
    )

    return values
