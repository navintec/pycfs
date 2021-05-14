
from setuptools import setup

setup(
    name='pycfs',
    version='1.0.0',
    packages=['pycfs'],
    install_requires=[
        'pyclibrary',
        'IPython'
        ],
    scripts=['scripts/cfssh'])
