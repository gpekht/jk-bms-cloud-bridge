import logging
import logging.handlers
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import jk_push


class LoggingTests(unittest.TestCase):
    def tearDown(self):
        root = logging.getLogger()
        for handler in root.handlers[:]:
            handler.close()
            root.removeHandler(handler)

    def test_error_log_is_small_and_has_one_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            log_dir = Path(directory)
            log_file = log_dir / "jk-bms.log"

            with (
                patch.object(jk_push, "LOG_DIR", log_dir),
                patch.object(jk_push, "LOG_FILE", log_file),
            ):
                jk_push.configure_logging()

            rotating_handlers = [
                handler
                for handler in logging.getLogger().handlers
                if isinstance(
                    handler,
                    logging.handlers.RotatingFileHandler,
                )
            ]
            self.assertEqual(len(rotating_handlers), 1)
            self.assertEqual(rotating_handlers[0].maxBytes, 128 * 1024)
            self.assertEqual(rotating_handlers[0].backupCount, 1)


if __name__ == "__main__":
    unittest.main()
