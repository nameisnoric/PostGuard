"""Local alert sound playback controlled by Desktop notification settings."""

import time
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QSoundEffect


DEFAULT_SETTINGS = {
    "notifications_enabled": True,
    "sound_enabled": True,
    "sound_volume": 70,
    "reminder_interval_minutes": 5,
}

ALERT_SOUND_PATH = (
    Path(__file__).resolve().parents[2]
    / "assets"
    / "sounds"
    / "posture_alert.wav"
)


class AlertSoundPlayer:
    """Presentation-only sound player.

    Alert timing belongs to Alert Policy v1.0.

    The sound player must NOT independently decide whether a
    new PostGuard alert is due. play_alert() therefore plays
    exactly once when upstream Alert Policy has already returned
    should_notify=True.

    notify() is preserved for compatibility with older Desktop
    tests/components, but the validated monitoring runtime uses
    play_alert().
    """

    def __init__(self, clock=None, effect_factory=None):
        self.clock = clock or time.monotonic
        self.effect_factory = effect_factory or QSoundEffect
        self.effect = None
        self.settings = DEFAULT_SETTINGS.copy()
        self.last_played_at = None

    def apply_settings(self, settings: dict) -> None:
        self.settings = {
            key: settings.get(key, default)
            for key, default in DEFAULT_SETTINGS.items()
        }

        if self.effect is not None:
            self.effect.setVolume(
                self.settings["sound_volume"]
                / 100.0
            )

        if not self._sound_allowed():
            self.last_played_at = None

    def play_alert(self) -> bool:
        """Play once because Alert Policy already approved this notification."""

        if not self._sound_allowed():
            return False

        self._play()
        self.last_played_at = self.clock()

        return True

    def notify(
        self,
        alert_active: bool,
        new_alert: bool = False,
    ) -> bool:
        """Legacy reminder behavior kept for compatibility only."""

        if not alert_active:
            self.last_played_at = None
            return False

        if not self._sound_allowed():
            return False

        now = self.clock()

        interval = (
            self.settings[
                "reminder_interval_minutes"
            ]
            * 60
        )

        due = (
            new_alert
            or self.last_played_at is None
            or now - self.last_played_at >= interval
        )

        if not due:
            return False

        self._play()
        self.last_played_at = now

        return True

    def test_sound(self) -> bool:
        if not self.settings["sound_enabled"]:
            return False

        self._play()

        return True

    def play_preview(self, volume: int) -> None:
        previous_volume = (
            self.settings["sound_volume"]
        )

        self.settings["sound_volume"] = max(
            0,
            min(
                100,
                int(volume),
            ),
        )

        self._play()

        self.settings[
            "sound_volume"
        ] = previous_volume

    def _sound_allowed(self) -> bool:
        return bool(
            self.settings["notifications_enabled"]
            and self.settings["sound_enabled"]
            and self.settings["sound_volume"] > 0
        )

    def _play(self) -> None:
        if self.effect is None:
            self.effect = self.effect_factory()

            self.effect.setSource(
                QUrl.fromLocalFile(
                    str(ALERT_SOUND_PATH)
                )
            )

            self.effect.setLoopCount(1)

        self.effect.setVolume(
            self.settings["sound_volume"]
            / 100.0
        )

        self.effect.play()