from setuptools import setup, find_packages

setup(
    name='brewblox-devcon-spark',
    use_scm_version={'local_scheme': lambda v: ''},
    long_description=open('README.md').read(),
    url='https://github.com/BrewBlox/brewblox-devcon-spark',
    author='BrewPi',
    author_email='Development@brewpi.com',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Programming Language :: Python :: 3.6',
        'Intended Audience :: End Users/Desktop',
        'Topic :: System :: Hardware',
    ],
    keywords='brewing brewpi brewblox embedded controller spark service',
    packages=find_packages(exclude=['test']),
    install_requires=[
        'brewblox-service~=0.9',
        'dpath~=1.4.2',
        'pyserial-asyncio==0.4',
        'construct==2.9.39',
        'deprecated==1.2.0',
        'protobuf==3.5.1',
        'tinydb==3.8.1.post1',
        'aiotinydb==1.1.0',
    ],
    python_requires='>=3.6',
    extras_require={'dev': ['tox']},
    setup_requires=['setuptools_scm'],
)
