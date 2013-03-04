#!/usr/bin/env python

import os, os.path
import subprocess
import signal, datetime
import logging
import heapq

def main():
    from apscheduler.scheduler import Scheduler

    try:
        from ConfigParser import ConfigParser
    except ImportError: # python3
        from configparser import ConfigParser

    try:
        config = ConfigParser(inline_comment_prefixes=(';',))
    except TypeError: # not python3
        config = ConfigParser()

    config.readfp(open('config-file'))
    global logfile
    logfile = config.get("global", "logfile")
    FORMAT = "%(asctime)-15s: %(message)s"
    logging.basicConfig(level=logging.INFO, filename=logfile, filemode='w',
                        format=FORMAT)

    # Set time on WDLXTV systems
    rdate = "/usr/sbin/rdate"
    if os.path.exists(rdate) and os.access(rdate, os.X_OK):
        cmd = [rdate, "ntp.internode.on.net"]
        subprocess.Popen(cmd).wait()

    logging.info("Main process PID: %d, use this for sending SIGHUP "
                 "for re-reading the schedule-file", os.getpid())

    global tuners
    tuners = TUNERS(config.get("global", "tuners"))

    global hdhomerun_config
    hdhomerun_config = config.get("global", "hdhomerun_config")

    schedule_file = config.get("global", "schedule_file")
    media_dir = config.get("global", "media_dir")

    channelmap = {}
    for opt in config.options("channelmap"):
        channelmap[opt] = config.get("channelmap", opt).split(",")

    while True:
        global reload_jobs
        reload_jobs = False
        sched = Scheduler(misfire_grace_time=60, daemonic=False)
        sched.start()
        signal.signal(signal.SIGHUP, sighup_handler)
        schedule_jobs(sched, schedule_file, channelmap, media_dir)
        while not reload_jobs:
            signal.pause()
        sched.shutdown()

def sighup_handler(signum, frame):
    global reload_jobs
    reload_jobs = True

def schedule_jobs(sched, schedule_file, channelmap, media_dir):
    import shlex
    for line in open(schedule_file):
        try:
            (prog_name, start, period, vchannel, days) = shlex.split(line, True)
        except ValueError:
            if not line.strip() or line.strip().startswith('#'):
                continue    # Comment or a blank line
            else:
                logging.warning("Incorrect line:%s" % line) 
                continue

        FORMAT = "%Y-%m-%d %H:%M"
        start = datetime.datetime.strptime(start, FORMAT)
        if days == 'once' or days == '9': # FIXME compatibility issue
            repeat = False
        else:
            repeat = True
        (channel, subchannel) = channelmap[vchannel]
        period = int(period)
        job = JOB(media_dir, prog_name, start, period, channel, subchannel)

        if repeat:
            sched.add_cron_job(job.record, hour=start.hour,
                               minute=start.minute, second=0,
                               day_of_week=days, name=job.prog_name)
        else:
            # Don't schedule if it can never be run!
            now = datetime.datetime.now()
            if start > now:
                sched.add_cron_job(job.record, year=start.year,
                        month=start.month, day=start.day,
                        hour=start.hour, minute=start.minute,
                        second=0, name=job.prog_name)

class TUNERS:
    def __init__(self, str):
        from threading import Lock

        tuners = "".join(str.split()) # remove white space
        tuners = tuners.split(',')
        tuners = [tuple(x.split(':')[0:2]) for x in tuners]
        # Add priority
        self.tuner_list = [(i, v[0], v[1]) for i,v in enumerate(tuners)]
        heapq.heapify(self.tuner_list)
        self.lock = Lock()

    def get_tuner(self):
        self.lock.acquire()
        try:
            tuner = heapq.heappop(self.tuner_list)
        except IndexError:
            tuner = None
        finally:
            self.lock.release()
        return tuner

    def put_tuner(self, tuner):
        self.lock.acquire()
        heapq.heappush(self.tuner_list, tuner)
        self.lock.release()

class JOB:
    def __init__(self, basedir, prog_name, start, period, channel, subchannel):
        self.basedir = os.path.normpath(basedir)
        self.prog_name = prog_name
        self.start = start
        self.period = period
        # TODO: We should correct stripping at the source.
        self.channel = channel.strip()
        self.subchannel = subchannel.strip()

    def record(self):
        tuner = tuners.get_tuner()
        if tuner == None:
            return

        try:
            (prio, device_id, tuner_num) = tuner
            self._record(device_id, tuner_num)
        except:
            pass
        finally:
            tuners.put_tuner(tuner)
            return


    def _record(self, device_id, tuner_num):
        import time
        import tempfile

        logging.info("Started recording %s on device: (%s, %s, %s:%s)" % (
                     self.prog_name, device_id, tuner_num,
                     self.channel, self.subchannel))
        now = datetime.datetime.now()
        date = now.strftime("%Y-%m-%d")
        dirname = os.path.join(self.basedir, self.prog_name)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        filename = os.path.join(dirname, "%s.ts" % date)
        cmd = [hdhomerun_config, device_id, "set"]
        cmd.extend(["/tuner%s/channel" % tuner_num, self.channel])
        subprocess.Popen(cmd).wait()

        cmd = [hdhomerun_config, device_id, "set"]
        cmd.extend(["/tuner%s/program" % tuner_num, self.subchannel])
        subprocess.Popen(cmd).wait()

        cmd = [hdhomerun_config, device_id, "save"]
        cmd.extend(["/tuner%s" % tuner_num, filename])
        f = tempfile.TemporaryFile()
        p = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT)

        # Record from now to the end of the program.
        now = datetime.datetime.now()
        td = (datetime.datetime.combine(now.date(), self.start.time()) +
              datetime.timedelta(minutes=self.period) - now)
        timeleft = td.days * 24 * 60 * 60 + td.seconds
        time.sleep(timeleft)
        os.kill(p.pid, signal.SIGINT)
        p.wait()

        # Read the output from the save process
        f.seek(0)
        data = f.read()
        f.close()
        logging.info("Ended recording %s on device: (%s, %s, %s:%s), "
                     "status: %s" % (
                     self.prog_name, device_id, tuner_num,
                     self.channel, self.subchannel, data))

if __name__ == '__main__':
    main()
