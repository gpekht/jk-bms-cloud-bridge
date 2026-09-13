import asyncio
import logging
import logging.handlers
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from bms_reader import read_bms
from grafana_uploader import push_grafana
from thingspeak_uploader import push_thingspeak


BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = Path(os.getenv("JK_BMS_ENV_FILE", BASE_DIR / ".env"))
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "jk-bms.log"


def configure_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s "
        "%(levelname)s "
        "%(name)s: "
        "%(message)s"
    )

    # Persistent log: errors only
    file_handler = logging.handlers.RotatingFileHandler(
        str(LOG_FILE),
        maxBytes=2 * 1024 * 1024,
        backupCount=5,
    )
    file_handler.setLevel(logging.ERROR)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console / systemd journal: errors only
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.ERROR)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

def print_values(v):
    print()
    print(
        f'{v["voltage"]:.3f} V  '
        f'{v["current"]:+.3f} A  '
        f'{v["power"]:+.1f} W  '
        f'SOC {v["soc"]}%  '
        f'{v["remaining_ah"]:.2f} Ah  '
        f'Delta {v["cell_delta_mv"]:.0f} mV'
    )

    cells = "  ".join(
        f"{i}:{voltage:.3f}"
        for i, voltage in enumerate(
            v["cells"],
            start=1,
        )
    )

    print(f"Cells: {cells}")
    print()


async def main():
    load_dotenv(ENV_FILE)

    logger = logging.getLogger(__name__)

    logger.info("JK BMS collection started")

    try:
        values = await read_bms()

    except Exception:
        logger.exception("Could not read JK BMS")
        return 1

#    print_values(values)

    failures = []

    try:
        result = await asyncio.to_thread(
            push_thingspeak,
            values,
        )

        logger.info(
            "ThingSpeak complete: battery=%s cells=%s",
            result["battery_entry"],
            result["cells_entry"],
        )

    except Exception:
        logger.exception("ThingSpeak upload failed")
        failures.append("ThingSpeak")

    try:
        grafana_status = await asyncio.to_thread(
            push_grafana,
            values,
        )

        logger.info(
            "Grafana complete: HTTP %s",
            grafana_status,
        )

    except Exception:
        logger.exception("Grafana upload failed")
        failures.append("Grafana")

    if failures:
        logger.error(
            "Run finished with failed destinations: %s",
            ", ".join(failures),
        )

        return 2

    logger.info("JK BMS collection completed successfully")

    return 0


if __name__ == "__main__":
    configure_logging()

    exit_code = asyncio.run(main())
    raise SystemExit(exit_code)
