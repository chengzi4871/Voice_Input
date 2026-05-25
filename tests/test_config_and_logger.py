import logging
import tempfile
import unittest
from unittest.mock import patch

from core.config_manager import AppConfig
from core.logger import get_log_path, setup_logging


class ConfigAndLoggerTest(unittest.TestCase):
    def test_config_defaults_keep_logs_off_and_wechat_clipboard_enabled(self):
        config = AppConfig.from_dict({})

        self.assertEqual(config.log_level, "OFF")
        self.assertEqual(config.clipboard_app_names, ["wechat.exe", "weixin.exe"])

    def test_invalid_log_level_falls_back_to_off(self):
        config = AppConfig.from_dict({"log_level": "verbose"})

        self.assertEqual(config.log_level, "OFF")

    def test_empty_clipboard_app_list_is_preserved(self):
        config = AppConfig.from_dict({"clipboard_app_names": []})

        self.assertEqual(config.clipboard_app_names, [])

    def test_setup_logging_off_does_not_create_log_path(self):
        logger = setup_logging("OFF")

        self.assertTrue(logger.disabled)
        self.assertIsNone(get_log_path())

    def test_setup_logging_debug_enables_logger(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict("os.environ", {"APPDATA": tmp_dir}):
                logger = setup_logging("DEBUG")
                self.assertFalse(logger.disabled)
                self.assertEqual(logger.level, logging.DEBUG)
                setup_logging("OFF")



if __name__ == "__main__":
    unittest.main()
