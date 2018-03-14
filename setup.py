from setuptools import setup, find_packages

setup(
    name='brewblox-controller-spark',
    version='0.1.0',
    long_description=open('README.md').read(),
    url='https://github.com/BrewBlox/brewblox-controller-spark',
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
        'brewblox-service~=0.5'
    ],
    python_requires='>=3.6',
    extras_require={'dev': ['tox']}
)
