from setuptools import find_packages, setup

setup(
    name='brewblox-devcon-spark',
    use_scm_version={'local_scheme': lambda v: ''},
    description='Communication with Spark controllers',
    long_description=open('README.md').read(),
    url='https://github.com/BrewBlox/brewblox-devcon-spark',
    author='BrewPi',
    author_email='Development@brewpi.com',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Programming Language :: Python :: 3.7',
        'Intended Audience :: End Users/Desktop',
        'Topic :: System :: Hardware',
    ],
    license='GPLv3',
    keywords='brewing brewpi brewblox embedded controller spark service',
    packages=find_packages(exclude=['test']),
    install_requires=[
        'brewblox-service~=0.14.0',
        'dpath~=1.4.2',
        'pyserial-asyncio==0.4',
        'construct==2.9.45',
        'protobuf~=3.6.0',
        'pint~=0.8',
        'aiofiles~=0.4.0',
        'aiozeroconf~=0.1.7',
        'aiohttp-sse~=2.0',
    ],
    python_requires='>=3.7',
    setup_requires=['setuptools_scm'],
)
