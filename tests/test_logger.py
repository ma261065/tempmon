import contextlib
import io
import unittest
from unittest.mock import patch

from Logger import TemperatureLogger


class TemperatureLoggerTests(unittest.TestCase):
    def setUp(self):
        self.now = 1_000_000
        clock = patch("Logger.time.time", side_effect=lambda: self.now)
        clock.start()
        self.addCleanup(clock.stop)
        output = contextlib.redirect_stdout(io.StringIO())
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)

    def test_default_buffer_keeps_original_memory_budget(self):
        logger = TemperatureLogger()
        self.assertEqual(logger.max_readings, 2880)
        self.assertEqual(logger.record_size, 5)
        self.assertEqual(len(logger.buffer), 14400)

    def test_rollover_preserves_recent_absolute_timestamps(self):
        logger = TemperatureLogger(max_readings=10)
        epoch = self.now
        logger.add_reading("stale", 10)
        self.now = epoch + 65530 * 60
        logger.add_reading("sensor", 20)
        before = list(logger.stream_history_reverse("sensor"))
        self.now = epoch + 65536 * 60
        logger.add_reading("sensor", 21)
        self.assertEqual(list(logger.stream_history_reverse("sensor")),
                         [(self.now, 21.0)] + before)
        self.assertEqual(logger.get_sensor_data_count("stale"), 0)
        self.assertEqual(logger.get_sensor_data_count("sensor"), 2)
        self.assertEqual(logger.count, 2)
        self.assertEqual(len(logger.buffer), 50)

    def test_rollover_during_latest_reading_update(self):
        logger = TemperatureLogger(max_readings=10)
        epoch = self.now
        self.now = epoch + 65535 * 60
        logger.add_reading("sensor", 20)
        self.now += 60
        logger.add_reading("sensor", 21)
        self.assertEqual(logger.count, 1)
        self.assertEqual(list(logger.stream_history_reverse("sensor")),
                         [(self.now, 21.0)])

    def test_rollover_compacts_wrapped_full_ring(self):
        logger = TemperatureLogger(max_readings=4)
        epoch = self.now
        for minutes in (0, 5, 10, 15, 65530, 65535):
            self.now = epoch + minutes * 60
            logger.add_reading("sensor", minutes / 1000)
        before = list(logger.stream_history_reverse("sensor"))
        self.assertEqual(logger.count, 4)
        self.assertEqual(logger.head, logger.tail)
        self.now = epoch + 65540 * 60
        logger.add_reading("sensor", 22)
        self.assertEqual(list(logger.stream_history_reverse("sensor")),
                         [(self.now, 22.0)] + before[:2])
        self.assertEqual(logger.count, 3)
        self.assertEqual(logger.get_sensor_data_count("sensor"), 3)

    def test_long_gap_expires_history_and_next_rollover_works(self):
        logger = TemperatureLogger(max_readings=4)
        logger.add_reading("sensor", 20)
        for _ in range(2):
            self.now += 70000 * 60
            logger.add_reading("sensor", 21)
            self.assertEqual(list(logger.stream_history_reverse("sensor")),
                             [(self.now, 21.0)])
            self.assertEqual(logger.count, 1)

    def test_per_sensor_limit_keeps_other_sensors_in_full_ring(self):
        logger = TemperatureLogger(max_readings=4, min_interval_minutes=720)
        for sensor, temperature in (("a", 1), ("b", 10), ("a", 2),
                                    ("b", 11), ("a", 3)):
            logger.add_reading(sensor, temperature)
            self.now += 720 * 60
        self.assertEqual(logger.count, 4)
        self.assertEqual(logger.get_sensor_data_count("a"), 2)
        self.assertEqual(logger.get_sensor_data_count("b"), 2)
        self.assertEqual([value for _, value in logger.stream_history_reverse("a")],
                         [3.0, 2.0])
        self.assertEqual([value for _, value in logger.stream_history_reverse("b")],
                         [11.0, 10.0])


if __name__ == "__main__":
    unittest.main()
