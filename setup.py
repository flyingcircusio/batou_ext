"""A library of components for batou.
"""

import glob
import os.path

from setuptools import find_packages, setup


def project_path(*names):
    return os.path.join(*names)


setup(
    name="batou_ext",
    version="2.3.dev0",
    install_requires=[
        "batou >= 2.3b4",
        "pyaml",
        "setuptools",
        "six", ],
    extras_require={
        "test": [
            "boto3",
            "passlib>=1.7",
            "pytest",
            "pytest-mock", ], },
    author="Christian Theune <ct@flyingcircus.io>",
    author_email="ct@flyingcircus.io",
    license="BSD (2-clause)",
    url="https://plan.flyingcircus.io/projects/batou/",
    keywords="deployment",
    classifiers="""\
License :: OSI Approved :: BSD License
Programming Language :: Python
Programming Language :: Python :: 3
Programming Language :: Python :: 3.6
Programming Language :: Python :: 3.7
Programming Language :: Python :: 3.8
Programming Language :: Python :: 3.9
Programming Language :: Python :: 3 :: Only
"""[:-1].split("\n"),
    description=__doc__.strip(),
    long_description="\n\n".join(
        open(project_path(name)).read() for name in (
            "README.md",
            "CHANGES.txt",
            "HACKING.txt",
        )),
    packages=find_packages("src"),
    package_dir={"": "src"},
    include_package_data=True,
    data_files=[("", glob.glob(project_path("*.txt")))],
    entry_points=dict(console_scripts=[
        "jenkins = batou_ext.jenkins:main",
        "fcio = batou_ext.fcio:main", ]),
    zip_safe=False,
)
