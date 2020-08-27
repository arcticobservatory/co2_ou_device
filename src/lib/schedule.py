import utime

import timeutil

class ByMinute(object):
    def __init__(self, divisor, offset=0):
        self.divisor = divisor
        self.offset = offset

    def __str__(self):
        return "ByMinute({divisor}, offset={offset})".format(**self.__dict__)

    def check(self, tt):
        yy, mo, dd, hh, mm, *_ = tt
        return mm % self.divisor == self.offset

    def next(self, tt):
        yy, mo, dd, hh, mm, *_ = tt
        next_minutes = (mm // self.divisor) * self.divisor + self.offset
        if next_minutes <= mm:
            next_minutes += self.divisor
        next_tt = (yy, mo, dd, hh, next_minutes, 0, 0, 0)
        return timeutil.normalize(next_tt)

class ByTimeOfDay(object):
    def __init__(self, hour, minute):
        self.hour = hour
        self.minute = minute

    def __str__(self):
        return "ByTimeOfDay({hour:02d}:{minute:02d})".format(**self.__dict__)

    def check(self, tt):
        yy, mo, dd, hh, mm, *_ = tt
        return hh == self.hour and mm == self.minute

    def next(self, tt):
        yy, mo, dd, hh, mm = tt[0:5]
        if hh < self.hour or (hh == self.hour and mm < self.minute):
            next_tt = (yy, mo, dd, self.hour, self.minute, 0, 0, 0)
        else:
            next_tt = (yy, mo, dd+1, self.hour, self.minute, 0, 0, 0)

        return timeutil.normalize(next_tt)

class ScheduleException(Exception): pass

SCHED_STRS = {
        "minutes": ByMinute,
        "daily": ByTimeOfDay,
        }

class Schedule(object):
    def __init__(self, sched):
        self.sched = [[task, SCHED_STRS[sched_class](*args)]
                for task, sched_class, *args in sched]

    def check(self, tt):
        return [task for task, task_sched in self.sched if task_sched.check(tt)]

    def next(self, tt):
        agenda = [[task_sched.next(tt), task]
                    for task, task_sched in self.sched]
        agenda.sort()
        return agenda
