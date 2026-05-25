import unittest

from core.config_manager import HotkeyConfig, ProfileConfig
from core.windows_hotkey_hook import HotkeyEventProcessor, VK_LMENU, VK_MENU


VK_C = ord("C")
VK_X = ord("X")


def _profile(key: str, alt: bool = True) -> ProfileConfig:
    return ProfileConfig(
        name=f"Profile {key}",
        hotkey=HotkeyConfig(key=key, alt=alt),
        system_prompt="",
    )


class HotkeyEventProcessorTest(unittest.TestCase):
    def test_alt_x_triggers_only_when_complete_and_suppresses_trigger(self):
        started = []
        stopped = []
        processor = HotkeyEventProcessor(
            [_profile("x")],
            started.append,
            stopped.append,
        )

        self.assertFalse(processor.handle_key_event(VK_LMENU, True))
        self.assertEqual(started, [])

        self.assertTrue(processor.handle_key_event(VK_X, True))
        self.assertEqual(started, [0])

        self.assertTrue(processor.handle_key_event(VK_X, False))
        self.assertEqual(stopped, [0])

        self.assertFalse(processor.handle_key_event(VK_LMENU, False))

    def test_alt_c_suppresses_key_down_repeat_and_key_up_but_not_alt(self):
        started = []
        stopped = []
        processor = HotkeyEventProcessor(
            [_profile("c")],
            started.append,
            stopped.append,
        )

        self.assertFalse(processor.handle_key_event(VK_MENU, True))
        self.assertTrue(processor.handle_key_event(VK_C, True))
        self.assertTrue(processor.handle_key_event(VK_C, True))
        self.assertTrue(processor.handle_key_event(VK_C, False))
        self.assertFalse(processor.handle_key_event(VK_MENU, False))

        self.assertEqual(started, [0])
        self.assertEqual(stopped, [0])

    def test_releasing_modifier_stops_recording_without_suppressing_modifier(self):
        started = []
        stopped = []
        processor = HotkeyEventProcessor(
            [_profile("x")],
            started.append,
            stopped.append,
        )

        self.assertFalse(processor.handle_key_event(VK_LMENU, True))
        self.assertTrue(processor.handle_key_event(VK_X, True))
        self.assertFalse(processor.handle_key_event(VK_LMENU, False))
        self.assertFalse(processor.handle_key_event(VK_X, False))

        self.assertEqual(started, [0])
        self.assertEqual(stopped, [0])

    def test_profiles_can_be_rebuilt_with_new_hotkey(self):
        started = []
        stopped = []
        new_processor = HotkeyEventProcessor(
            [_profile("c")],
            started.append,
            stopped.append,
        )

        self.assertFalse(new_processor.handle_key_event(VK_LMENU, True))
        self.assertFalse(new_processor.handle_key_event(VK_X, True))
        self.assertEqual(started, [])

        self.assertTrue(new_processor.handle_key_event(VK_C, True))
        self.assertEqual(started, [0])


if __name__ == "__main__":
    unittest.main()
