import unittest
from unittest.mock import patch

from core import text_input


class SendTextTest(unittest.TestCase):
    def test_send_text_uses_clipboard_for_wechat(self):
        with (
            patch.object(
                text_input,
                "should_use_clipboard_for_foreground_window",
                return_value=True,
            ),
            patch.object(text_input, "paste_unicode") as paste_unicode,
            patch.object(text_input, "send_unicode") as send_unicode,
        ):
            self.assertEqual(text_input.send_text("hello"), "clipboard")

        paste_unicode.assert_called_once_with("hello")
        send_unicode.assert_not_called()

    def test_send_text_uses_unicode_for_other_windows(self):
        with (
            patch.object(
                text_input,
                "should_use_clipboard_for_foreground_window",
                return_value=False,
            ),
            patch.object(text_input, "paste_unicode") as paste_unicode,
            patch.object(text_input, "send_unicode") as send_unicode,
        ):
            self.assertEqual(text_input.send_text("hello"), "unicode")

        send_unicode.assert_called_once_with("hello")
        paste_unicode.assert_not_called()

    def test_configure_clipboard_app_names_normalizes_names(self):
        original = text_input.get_clipboard_app_names()
        try:
            text_input.configure_clipboard_app_names([
                "WeChat",
                r"C:\Apps\DingTalk.exe",
            ])
            self.assertEqual(
                text_input.get_clipboard_app_names(),
                ["dingtalk.exe", "wechat.exe"],
            )
        finally:
            text_input.configure_clipboard_app_names(original)


if __name__ == "__main__":
    unittest.main()
