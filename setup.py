from __future__ import with_statement

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


def readme():
    with open('README.rst') as f:
        return f.read()


setup(
    name='warp-proxy',
    version='0.1.0',
    description='Simple http transparent proxy made in Python 3.4',
    long_description=readme(),
    url='https://github.com/devunt/warp',
    author='JuneHyeon Bae',
    author_email='devunt' '@' 'gmail.com',
    license='MIT License',
    py_modules=['warp'],
    entry_points='''
        [console_scripts]
        warp = warp:main
    ''',  # for setuptools
    scripts=['warp.py'],  # for distutils without setuptools
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Environment :: Web Environment',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: Implementation :: CPython',
        'Topic :: Internet :: Proxy Servers',
        'Topic :: Internet :: WWW/HTTP',
    ]
)
