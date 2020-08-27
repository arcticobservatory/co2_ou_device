import unittest

import utime

import timeutil

class TestParseAndFormat(unittest.TestCase):

    def test_parse_time(self):
        self.assertEqual(timeutil.parse_time("2020-08-27 00:19:23"),
                (2020, 8, 27, 0, 19, 23, 0, 0))

        self.assertEqual(timeutil.parse_time("2020-08-27"),
                (2020, 8, 27, 0, 0, 0, 0, 0))

        with self.assertRaises(ValueError):
            timeutil.parse_time("200x")

    def test_format_time(self):
        tt = (2020, 8, 27, 0, 19, 23)
        self.assertEqual(timeutil.format_time(tt), "2020-08-27 00:19:23")

class TestCalendarFns(unittest.TestCase):

    def test_leap_year(self):
        self.assertEqual( timeutil.isleapyear(2001), False)
        self.assertEqual( timeutil.isleapyear(2020), True)
        self.assertEqual( timeutil.isleapyear(1700), False)
        self.assertEqual( timeutil.isleapyear(2000), True)

    def test_mktime_localtime_known_time(self):
        tt = timeutil.parse_time("2020-08-27 01:53:24")
        ts = 1598493204
        self.assertEqual( timeutil.localtime(ts)[0:6], tt[0:6])
        self.assertEqual( timeutil.mktime(tt), ts)

    def rollover_trial(self, tti, tte):
        self.assertEqual( timeutil.mktime(tti), timeutil.mktime(tte))
        self.assertEqual( timeutil.normalize(tti)[0:6], tte[0:6])

    def test_mktime_rollover(self):
        self.rollover_trial(
                (2020,8,27,1,53,60,0,0),
                (2020,8,27,1,54,0,0,0))
        self.rollover_trial(
                (2020,8,27,1,60,0,0,0),
                (2020,8,27,2,00,0,0,0))
        self.rollover_trial(
                (2020,8,27,24,0,0,0,0),
                (2020,8,28,0,0,0,0,0))
        self.rollover_trial(
                (2020,8,32,0,0,0,0,0),
                (2020,9,1,0,0,0,0,0))
        self.rollover_trial(
                (2020,13,1,0,0,0,0,0),
                (2021,1,1,0,0,0,0,0))
        self.rollover_trial(
                (2020,14,1,0,0,0,0,0),
                (2021,2,1,0,0,0,0,0))
        self.rollover_trial(
                (2020,12,31,23,59,60,0,0),
                (2021,1,1,0,0,0,0,0))
