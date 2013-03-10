#!/usr/bin/env python

import sys, os.path
from subprocess import Popen, PIPE

def channel_iter(file):
    for line in file:
        if line.startswith("SCANNING: "):
            channel = line.split()[2].strip('()')
            channel = channel.split(':')[1]
        elif line.startswith("LOCK: "):
            modulation = line.split()[1]
        elif line.startswith("PROGRAM "):
            (PROGRAM, subchannel, vchannel, name) = line.split(None, 3)
            subchannel = subchannel.rstrip(':')
            name = name.strip()     # remove new line
            name = name.replace(' ', '-')
            yield (vchannel, modulation, channel, subchannel, name)


def channel_info(hdhomerun_config, device_id, tuner):
    import tempfile

    f = tempfile.TemporaryFile("w+")
    cmd = [hdhomerun_config, device_id, "scan", "/tuner%s" % tuner] 
    p = Popen(cmd, stdout=f)
    p.wait()
    f.seek(0)
    return list(channel_iter(f))

def get_input(msg, func):
    while True:
        if sys.version_info[0] < 3:
            answer = raw_input("%s: " % msg)
        else: #python3
            answer = input("%s: " % msg)
        answer = answer.strip()
        if func(answer):
            return answer

def validate_executable(path):
    if not os.path.exists(path):
        print("%s doesn't exist\n" % path)
        return False
    if not os.path.isfile(path):
        print("%s is not a regular file\n" % path)
    if not os.access(path, os.X_OK):
        print("%s is not an executable\n" % path)
        return False
    else:
        return True

def validate_writable_directory(path):
    if not os.path.exists(path):
        print("%s doesn't exist\n" % path)
        return False
    if not os.path.isdir(path):
        print("%s is not a directory\n" % path)
        return False
    if not os.access(path, os.W_OK):
        print("%s is not a writable directory\n" % path)
        return False
    else:
        return True

def validate_logfile(path):
    if not os.path.exists(path):
        if validate_writable_directory(os.path.dirname(path)):
            return True
        else:
            return False
    if not os.path.isfile(path):
        print("%s is not a regular file\n" % path)
        return False
    if not os.access(path, os.W_OK):
        print("%s is not a writable file\n" % path)
        return False
    else:
        return True

def validate_readable_file(path):
    if not os.path.exists(path):
        print("%s doesn't exist\n" % path)
        return False
    if not os.path.isfile(path):
        print("%s is not a regular file\n" % path)
        return False
    if not os.access(path, os.R_OK):
        print("%s is not readable\n" % path)
        return False
    else:
        return True

def validate_tuners(tuners):
    if tuners == "0" or tuners == "1" or tuners == "0,1":
        return True
    else:
        return False

class HDHR:
    def __init__(self):
        self.get_hdhomerun_config()
        self.get_deviceid()
    def get_hdhomerun_config(self):
        msg = "Please provide path to hdhomerun_config binary"
        answer = get_input(msg, validate_executable)
        self.hdhomerun_config = os.path.abspath(answer)
    def get_deviceid(self):
        cmd = [self.hdhomerun_config, "discover"]
        p = Popen(cmd, stdout=PIPE, stderr=PIPE)
        out, err = p.communicate()
        # Check status rather than err file!
        if err:
            err = err.decode()
            sys.exit("Unable to run command: '%s' % cmd, error: 'err'" % (cmd,
                     err), "bailing out")
        out = out.decode().strip()
        if out.find("no devices found") != -1:
            sys.exit("Unable to find any hdhomerun device")
        out = out.split('\n')
        if len(out) == 1:
            import re
            mo = re.match("hdhomerun device (\S+) found", out[0])
            if mo:
                self.deviceid = mo.group(1)
            else:
                sys.exit("Unable to parse command: '%s' output:%s" % (cmd,
                    out[0]))
        else:
            msg = "You have multiple hdhomerun adapters. Disconnect all of "
            msg += "them except the one you want to use for recording and "
            msg += "then re-run this program."
            sys.exit(msg)

    def get_mediadir(self):
        msg = "Please provide the directory where you want to store "
        msg += "all your video recordings"
        answer = get_input(msg, validate_writable_directory)
        self.mediadir = os.path.abspath(answer)
    def get_logfile(self):
        msg = "Please provide logfile name for logging recording information"
        answer = get_input(msg, validate_logfile)
        self.logfile = os.path.abspath(answer)
    def get_schedulefile(self):
        msg = "Please provide schedule file that will be used for recording "
        msg += "programs"
        answer = get_input(msg, validate_readable_file)
        self.schedulefile = os.path.abspath(answer)
    def get_tuners(self):
        msg = "Provide tuners to use for recording. "
        msg += "If you have a single tuner adapter, provide 0. "
        msg += "If you have a dual tuner adapter, provide 0 to use tuner0 "
        msg += "for recording; provide 1 to use tuner1 for recording; "
        msg += "provide 0,1 to use both tuners for recording"
        answer = get_input(msg, validate_tuners)
        tuners = answer.split(',')
        self.scantuner = tuners[0]
        tuners = [self.deviceid+":"+x for x in tuners]
        self.tuners = ",".join(tuners)

def main():
    if len(sys.argv) != 2:
        sys.exit("usage: %s <output-file>" % sys.argv[0])
    conf = open(sys.argv[1], "w")
    hdhr = HDHR()
    hdhr.get_mediadir()
    hdhr.get_logfile()
    hdhr.get_schedulefile()
    hdhr.get_tuners()

    chan_info = channel_info(hdhr.hdhomerun_config, hdhr.deviceid,
                             hdhr.scantuner)
    if not len(chan_info):
        sys.exit("couldn't find any channels, quitting!")

    import datetime
    out = """# Generated by hdhomerun_setup script at %s
#
# Follows Python's configparser syntax. Characters '#' or ';' can
# start a comment. In line comment must be started with ';' though
""" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conf.write(out+"\n")
    conf.write("[global]\n")
    conf.write("logfile = %s\n" % hdhr.logfile)
    conf.write("media_dir = %s\n" % hdhr.mediadir)
    conf.write("schedule_file = %s\n" % hdhr.schedulefile)
    out = "hdhomerun_config = %s" % hdhr.hdhomerun_config
    out += " ;hdhomerun executable binary file\n"
    conf.write(out)
    out = """
# Provide device id and tuner numbers used for recording. Device id is
# whatever "hdhomerun_config discover" returned. It can be IP address
# of the hdhomerun network tuner as well if you use static IP address.
# E.g: 10306B1C:0,10306B1C:1 or 192.168.1.16:0,192.168.1.16:1
"""
    conf.write(out)
    conf.write("tuners = %s\n" % hdhr.tuners)
    conf.write("\n[channelmap]\n")
    conf.write("#virtual-channel = physical-channel program-number ;name-of-program\n")
    for (vchannel, modulation, channel, subchannel, name) in chan_info:
        line = "%-6s = %s:%s, %s\t;%s\n" % (vchannel, modulation, channel,
                                           subchannel, name)
        if vchannel != '0':
            conf.write(line)

if __name__ == '__main__':
    main()
