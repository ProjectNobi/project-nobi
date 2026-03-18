import re
import os
import codecs
from os import path
from io import open
from setuptools import setup, find_packages


def read_requirements(path):
    with open(path, "r") as f:
        requirements = f.read().splitlines()
        processed = []
        for req in requirements:
            if req.startswith("git+") or "@" in req:
                pkg_name = re.search(r"(#egg=)([\w\-_]+)", req)
                if pkg_name:
                    processed.append(pkg_name.group(2))
            elif req.strip() and not req.startswith("#"):
                processed.append(req)
        return processed


requirements = read_requirements("requirements.txt")
here = path.abspath(path.dirname(__file__))

with open(path.join(here, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

with codecs.open(
    os.path.join(here, "nobi/__init__.py"), encoding="utf-8"
) as init_file:
    version_match = re.search(
        r"^__version__ = ['\"]([^'\"]*)['\"]", init_file.read(), re.M
    )
    version_string = version_match.group(1)

setup(
    name="project-nobi",
    version=version_string,
    description="Project Nobi — Bittensor subnet for personal AI companions",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ProjectNobi/project-nobi",
    author="Kooltek68 team",
    packages=find_packages(),
    include_package_data=True,
    license="MIT",
    python_requires=">=3.9",
    install_requires=requirements,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
)
