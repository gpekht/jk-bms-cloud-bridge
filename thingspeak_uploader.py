import logging
import os

import requests

logger = logging.getLogger(__name__)

THINGSPEAK_URL = "https://api.thingspeak.com/update.json"


def push_thingspeak(values):
    battery_key = os.getenv("THINGSPEAK_BATTERY_KEY")
    cells_key = os.getenv("THINGSPEAK_CELLS_KEY")

    if not battery_key or not cells_key:
        raise RuntimeError(
            "ThingSpeak API keys are missing from environment"
        )

    battery_payload = {
        "api_key": battery_key,
        "field1": values["voltage"],
        "field2": values["current"],
        "field3": values["power"],
        "field4": values["soc"],
        "field5": values["remaining_ah"],
        "field6": values["temp1"],
        "field7": values["mosfet_temp"],
        "field8": values["cell_delta_mv"],
    }

    logger.info("Uploading battery summary to ThingSpeak")

    try:
        response = requests.post(
            THINGSPEAK_URL,
            data=battery_payload,
            timeout=15,
        )

        response.raise_for_status()
        battery_result = response.json()

        if not battery_result or "entry_id" not in battery_result:
            raise RuntimeError(
                f"Unexpected ThingSpeak battery response: "
                f"{battery_result}"
            )

        battery_entry = battery_result["entry_id"]

    except Exception:
        logger.exception("ThingSpeak battery upload failed")
        raise

    cells = values["cells"]

    if len(cells) != 8:
        raise RuntimeError(
            f"Expected 8 cells, got {len(cells)}"
        )

    cells_payload = {
        "api_key": cells_key,
        "field1": cells[0],
        "field2": cells[1],
        "field3": cells[2],
        "field4": cells[3],
        "field5": cells[4],
        "field6": cells[5],
        "field7": cells[6],
        "field8": cells[7],
    }

    logger.info("Uploading cell voltages to ThingSpeak")

    try:
        response = requests.post(
            THINGSPEAK_URL,
            data=cells_payload,
            timeout=15,
        )

        response.raise_for_status()
        cells_result = response.json()

        if not cells_result or "entry_id" not in cells_result:
            raise RuntimeError(
                f"Unexpected ThingSpeak cells response: "
                f"{cells_result}"
            )

        cells_entry = cells_result["entry_id"]

    except Exception:
        logger.exception("ThingSpeak cells upload failed")
        raise

    logger.info(
        "ThingSpeak upload OK: battery=%s cells=%s",
        battery_entry,
        cells_entry,
    )

    return {
        "battery_entry": battery_entry,
        "cells_entry": cells_entry,
    }

