#!/usr/bin/env python

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
    import subprocess
    import tempfile

    f = tempfile.TemporaryFile()
    cmd = [hdhomerun_config, device_id, "scan", "/tuner%d" % tuner] 
    p = subprocess.Popen(cmd, stdout=f)
    p.wait()
    f.seek(0)
    return list(channel_iter(f))

def main():
    import sys, os, os.path

    usage = ("usagde: %s path-to-hdhomerun-config device-id tuner-number"
             % sys.argv[0])
    if len(sys.argv) != 4:
        sys.exit(usage)
    hdhomerun_config = sys.argv[1]
    device_id = sys.argv[2]
    tuner = int(sys.argv[3])
    if not os.path.exists(hdhomerun_config):
        sys.exit("%s doesn't exist, aborting!")
    if not os.path.isfile(hdhomerun_config):
        sys.exit("%s is not a regular file, aborting!")
    if not os.access(hdhomerun_config, os.X_OK):
        sys.exit("%s doesn't have execute permission set, aborting!")

    chan_info = channel_info(hdhomerun_config, device_id, tuner)
    if not len(chan_info):
        sys.exit("couldn't find any channels, quitting!")

    print("[global]")
    print("logfile = logfile")
    print("media_dir = media")
    print("schedule_file = schedule-file")
    print("hdhomerun_config = %s" % hdhomerun_config)
    print("tuners = %s:%s" % (device_id, tuner))
    print("[channelmap]")
    print("#virtual-channel = physical-channel program-number ;name-of-program")
    for (vchannel, modulation, channel, subchannel, name) in chan_info:
        line = "%-6s = %s:%s, %s\t;%s" % (vchannel, modulation, channel,
                                           subchannel, name)
        if vchannel != '0':
            print(line)

if __name__ == '__main__':
    main()
