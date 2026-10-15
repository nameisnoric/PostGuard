import unittest

from app.services.alert_sound import AlertSoundPlayer


class FakeEffect:
    def __init__(self):
        self.source = None
        self.loop_count = None
        self.volume = None
        self.play_count = 0

    def setSource(self, source):
        self.source = source

    def setLoopCount(self, count):
        self.loop_count = count

    def setVolume(self, volume):
        self.volume = volume

    def play(self):
        self.play_count += 1


class AlertSoundPlayerTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.effect = FakeEffect()
        self.player = AlertSoundPlayer(
            clock=lambda: self.now,
            effect_factory=lambda: self.effect,
        )

    def test_new_alert_plays_at_selected_volume_and_repeats_when_due(self):
        self.player.apply_settings({
            "notifications_enabled": True,
            "sound_enabled": True,
            "sound_volume": 40,
            "reminder_interval_minutes": 5,
        })

        self.assertTrue(self.player.notify(True, new_alert=True))
        self.assertEqual(self.effect.volume, 0.4)
        self.assertEqual(self.effect.play_count, 1)
        self.now += 299
        self.assertFalse(self.player.notify(True))
        self.now += 1
        self.assertTrue(self.player.notify(True))
        self.assertEqual(self.effect.play_count, 2)

    def test_disabled_notifications_sound_or_zero_volume_are_silent(self):
        for change in (
            {"notifications_enabled": False},
            {"sound_enabled": False},
            {"sound_volume": 0},
        ):
            settings = {
                "notifications_enabled": True,
                "sound_enabled": True,
                "sound_volume": 70,
                "reminder_interval_minutes": 1,
                **change,
            }
            with self.subTest(change=change):
                self.player.apply_settings(settings)
                self.assertFalse(self.player.notify(True, new_alert=True))
        self.assertEqual(self.effect.play_count, 0)

    def test_alert_end_resets_reminder_cycle(self):
        self.player.notify(True, new_alert=True)
        self.player.notify(False)
        self.now += 1
        self.assertTrue(self.player.notify(True))
        self.assertEqual(self.effect.play_count, 2)


if __name__ == "__main__":
    unittest.main()
