from distutils.core import setup

setup(
    name='hdhomerun-recorder',
    version='0.1.0',
    author='Malahal Naineni',
    author_email='malahal@gmail.com',
    description='hdhomerun network tuner recorder',
    long_description=open('README').read(),
    url='http://pypi.python.org/pypi/hdhomerun-recorder/',

    requires=["apscheduler"],
    packages=['hdhomerun_recorder'],
    scripts=['scripts/hdhomerun_recorder', 'scripts/hdhomerun_recorder_setup'],
    data_files = [('/etc/hdhomerun_recorder',
                    ['data/config-file.example', 'data/schedule-file.example',
                        'data/hdhomerun_recorder.service'])]
)
