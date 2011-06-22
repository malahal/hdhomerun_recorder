from distutils.core import setup

setup(
    name='hdhomerun-recorder',
    version='0.1.0',
    author='Malahal Naineni',
    author_email='malahal@gmail.com',
    py_modules=['hdhomerun_recorder'],
    scripts=['scripts/hdhomerun_recorder', 'scripts/hdhomerun_recorder_setup'],
    url='http://pypi.python.org/pypi/hdhomerun-recorder/',
    description='hdhomerun network tuner recorder',
    long_description=open('README').read(),
    #zip_safe=False,
    #package_data={'hdhomerun.recorder': ['config-file-example']},
)
