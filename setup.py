"""A library of components for batou.
"""

import glob
import os.path

from setuptools import find_packages, setup


def project_path(*names):
    return os.path.join(*names)


setup(
    name="batou_ext",
    version="2.4.8",
    install_requires=[
        "batou >= 2.3b4",
        "pyaml",
        "setuptools",
        "six",
        "InquirerPy",
    ],
    extras_require={
        "test": [
            "boto3",
            "passlib>=1.7",
            "pytest",
            "pytest-mock",
        ],
        "version-select": ["InquirerPy"],
        "s3-bootstrap": ["boto3", "InquirerPy"],
    },
    author="Flying Circus <support@flyingcircus.io>",
    author_email="support@flyingcircus.io",
    license="BSD (2-clause)",
    url="https://github.com/flyingcircusio/batou_ext",
    keywords="deployment",
    classifiers="""\
License :: OSI Approved :: BSD License
Programming Language :: Python
Programming Language :: Python :: 3
Programming Language :: Python :: 3 :: Only
"""[
        :-1
    ].split(
        "\n"
    ),
    description=__doc__.strip(),
    long_description="\n\n".join(
        open(project_path(name)).read()
        for name in (
            "README.md",
            "CHANGES.md",
        )
    ),
    long_description_content_type="text/markdown",
    packages=find_packages("src"),
    package_dir={"": "src"},
    include_package_data=True,
    data_files=[("", glob.glob(project_path("*.txt")))],
    entry_points=dict(
        console_scripts=[
            "jenkins = batou_ext.jenkins:main",
            "fcio = batou_ext.fcio:main",
            "versions = batou_ext.versions:main",
            "s3_bootstrap = batou_ext.s3_bootstrap:main [s3-bootstrap]",
        ]
    ),
    zip_safe=False,
)
