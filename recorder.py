#!/usr/bin/env python

import os, os.path
import subprocess, time
import signal, datetime
import logging

def main():
    from apscheduler.scheduler import Scheduler
    from ConfigParser import ConfigParser

    config = ConfigParser()
    config.readfp(open('config-file'))
    logfile = config.get("global", "logfile")
    FORMAT = "%(asctime)-15s: %(message)s"
    logging.basicConfig(level=logging.INFO, filename=logfile, filemode='w',
                        format=FORMAT)

    # correct time on WDLXTV system, may fail on others 
    cmd = ["rdate", "ntp.internode.on.net"]
    subprocess.Popen(cmd).wait()

    logging.info("Main process PID: %d, use this for sending SIGHUP "
                 "for re-reading the schedule-file", os.getpid())

    tuners = config.get("global", "tuners")
    tuners = tuners.split(',')
    global tuner_list
    tuner_list = [x.split(':') for x in tuners]
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
        # TODO: Use multiple tuners. For now, use the first one
        # TODO: We should correct stripping at the source.
        device_id = tuner_list[0][0].strip()
        tuner_num = tuner_list[0][1].strip()

        now = datetime.datetime.now()
        FORMAT = "%Y-%m-%d %H:%M"
        logging.info("Recording %s at %s on channel:(%s,%s)" % (
                     self.prog_name, now.strftime(FORMAT),
                     self.channel, self.subchannel))
        date = now.strftime("%Y-%m-%d")
        dirname = os.path.join(self.basedir, self.prog_name)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        filename = os.path.join(dirname, "%s.ts" % date)
        cmd = [hdhomerun_config, device_id, "set"]
        cmd.append(os.path.join("/tuner%s" % tuner_num, "channel"))
        cmd.append(self.channel)
        subprocess.Popen(cmd).wait()

        cmd = [hdhomerun_config, device_id, "set"]
        cmd.append(os.path.join("/tuner%s" % tuner_num, "program"))
        cmd.append(self.subchannel)
        subprocess.Popen(cmd).wait()

        cmd = [hdhomerun_config, device_id, "save"]
        cmd.append(os.path.join("/tuner%s" % tuner_num))
        cmd.append(filename)
        p = subprocess.Popen(cmd)

        # Record from now to the end of the program.
        now = datetime.datetime.now()
        td = (datetime.datetime.combine(now.date(), self.start.time()) +
              datetime.timedelta(minutes=self.period) - now)
        timeleft = td.days * 24 * 60 * 60 + td.seconds
        time.sleep(timeleft)
        os.kill(p.pid, signal.SIGKILL)

if __name__ == '__main__':
    main()
