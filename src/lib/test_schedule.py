import utime

import unittest

import timeutil
import schedule

def parse_time(iso):
    return timeutil.normalize(timeutil.parse_time(iso))

class TestByMinute(unittest.TestCase):

    def test_str(self):
        sched = schedule.ByMinute(5)
        str(sched)

    def test_seconds_before(self):
        sched = schedule.ByMinute(5)
        tt      = parse_time("2020-08-27 00:19:23")
        next_tt = parse_time("2020-08-27 00:20:00")
        self.assertEqual(sched.check(tt), False)
        self.assertEqual(sched.next(tt), next_tt)

    def test_on_dot(self):
        sched = schedule.ByMinute(5)
        tt      = parse_time("2020-08-27 00:20:00")
        next_tt = parse_time("2020-08-27 00:25:00")
        self.assertEqual(sched.check(tt), True)
        self.assertEqual(sched.next(tt), next_tt)

    def test_with_offset(self):
        sched = schedule.ByMinute(5, offset=1)
        tt      = parse_time("2020-08-27 00:20:23")
        next_tt = parse_time("2020-08-27 00:21:00")
        self.assertEqual(sched.check(tt), False)
        self.assertEqual(sched.next(tt), next_tt)

    def test_with_offset_on_dot(self):
        sched = schedule.ByMinute(5, offset=1)
        tt      = parse_time("2020-08-27 00:21:00")
        next_tt = parse_time("2020-08-27 00:26:00")
        self.assertEqual(sched.check(tt), True)
        self.assertEqual(sched.next(tt), next_tt)

    def test_rollover(self):
        sched = schedule.ByMinute(5)
        tt      = parse_time("2020-08-27 00:59:23")
        next_tt = parse_time("2020-08-27 01:00:00")
        self.assertEqual(sched.check(tt), False)
        self.assertEqual(sched.next(tt), next_tt)

    def test_with_offset_rollover(self):
        sched = schedule.ByMinute(5, offset=1)
        tt      = parse_time("2020-08-27 00:57:00")
        next_tt = parse_time("2020-08-27 01:01:00")
        self.assertEqual(sched.check(tt), False)
        self.assertEqual(sched.next(tt), next_tt)

class TestByTimeOfDay(unittest.TestCase):

    def test_str(self):
        sched = schedule.ByTimeOfDay(3, 15)
        str(sched)

    def test_greater_hour_greater_minute(self):
        sched = schedule.ByTimeOfDay(3, 15)
        tt      = parse_time("2020-08-27 05:45:00")
        next_tt = parse_time("2020-08-28 03:15:00")
        self.assertEqual(sched.check(tt), False)
        self.assertEqual(sched.next(tt), next_tt)

    def test_greater_hour_same_minute(self):
        sched = schedule.ByTimeOfDay(3, 15)
        tt      = parse_time("2020-08-27 05:15:00")
        next_tt = parse_time("2020-08-28 03:15:00")
        self.assertEqual(sched.check(tt), False)
        self.assertEqual(sched.next(tt), next_tt)

    def test_greater_hour_lesser_minute(self):
        sched = schedule.ByTimeOfDay(3, 15)
        tt      = parse_time("2020-08-27 05:10:00")
        next_tt = parse_time("2020-08-28 03:15:00")
        self.assertEqual(sched.check(tt), False)
        self.assertEqual(sched.next(tt), next_tt)

    def test_same_hour_greater_minute(self):
        sched = schedule.ByTimeOfDay(3, 15)
        tt      = parse_time("2020-08-27 03:45:00")
        next_tt = parse_time("2020-08-28 03:15:00")
        self.assertEqual(sched.check(tt), False)
        self.assertEqual(sched.next(tt), next_tt)

    def test_same_hour_same_minute(self):
        sched = schedule.ByTimeOfDay(3, 15)
        tt      = parse_time("2020-08-27 03:15:00")
        next_tt = parse_time("2020-08-28 03:15:00")
        self.assertEqual(sched.check(tt), True)
        self.assertEqual(sched.next(tt), next_tt)

    def test_same_hour_lesser_minute(self):
        sched = schedule.ByTimeOfDay(3, 15)
        tt      = parse_time("2020-08-27 03:10:00")
        next_tt = parse_time("2020-08-27 03:15:00")
        self.assertEqual(sched.check(tt), False)
        self.assertEqual(sched.next(tt), next_tt)

    def test_lesser_hour_greater_minute(self):
        sched = schedule.ByTimeOfDay(3, 15)
        tt      = parse_time("2020-08-27 02:45:00")
        next_tt = parse_time("2020-08-27 03:15:00")
        self.assertEqual(sched.check(tt), False)
        self.assertEqual(sched.next(tt), next_tt)

    def test_lesser_hour_same_minute(self):
        sched = schedule.ByTimeOfDay(3, 15)
        tt      = parse_time("2020-08-27 02:15:00")
        next_tt = parse_time("2020-08-27 03:15:00")
        self.assertEqual(sched.check(tt), False)
        self.assertEqual(sched.next(tt), next_tt)

    def test_lesser_hour_lesser_minute(self):
        sched = schedule.ByTimeOfDay(3, 15)
        tt      = parse_time("2020-08-27 02:10:00")
        next_tt = parse_time("2020-08-27 03:15:00")
        self.assertEqual(sched.check(tt), False)
        self.assertEqual(sched.next(tt), next_tt)

class TestScheduleCalculations(unittest.TestCase):

    def test_sched(self):
        sched = schedule.Schedule([
                    ["Communicate", 'daily', 3, 15],
                    ["TakeMeasurement", 'minutes', 30, 0],
                ])

        tt = parse_time("2020-08-27 01:53:20")
        self.assertEqual( sched.check(tt), [] )
        self.assertEqual( sched.next(tt), [
            [parse_time("2020-08-27 02:00:00"), "TakeMeasurement"],
            [parse_time("2020-08-27 03:15:00"), "Communicate"],
            ])

        tt = parse_time("2020-08-27 03:00:00")
        self.assertEqual( sched.check(tt), ["TakeMeasurement"] )
        self.assertEqual( sched.next(tt), [
            [parse_time("2020-08-27 03:15:00"), "Communicate"],
            [parse_time("2020-08-27 03:30:00"), "TakeMeasurement"],
            ])

        tt = parse_time("2020-08-27 03:15:00")
        self.assertEqual( sched.check(tt), ["Communicate"] )
        self.assertEqual( sched.next(tt), [
            [parse_time("2020-08-27 03:30:00"), "TakeMeasurement"],
            [parse_time("2020-08-28 03:15:00"), "Communicate"],
            ])
