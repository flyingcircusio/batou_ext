"""A library of components for batou.
"""

from setuptools import setup, find_packages
import glob
import os.path


def project_path(*names):
    return os.path.join(*names)


setup(
    name='batou_ext',
    version='0.1dev0',
    install_requires=[
        'batou>=1.0b20',
        'pyaml',
        'setuptools',
    ],
    extras_require={
        'test': [
        ],
    },
    author='Christian Theune <ct@flyingcircus.io>',
    author_email='ct@flyingcircus.io',
    license='BSD (2-clause)',
    url='https://plan.flyingcircus.io/projects/batou/',
    keywords='deployment',
    classifiers="""\
License :: OSI Approved :: BSD License
Programming Language :: Python
Programming Language :: Python :: 2
Programming Language :: Python :: 2.7
Programming Language :: Python :: 2 :: Only
"""[:-1].split('\n'),
    description=__doc__.strip(),
    long_description='\n\n'.join(open(project_path(name)).read() for name in (
        'README',
        'CHANGES.txt',
        'HACKING.txt',
        )),
    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    data_files=[('', glob.glob(project_path('*.txt')))],
    entry_points=dict(console_scripts=[
        'jenkins = batou_ext.jenkins:main',
        'fcio = batou_ext.fcio:main',
    ]),
    zip_safe=False,
)
