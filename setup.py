"""The setup script."""

from setuptools import find_packages, setup
from deeppath import __version__

with open("README.rst") as readme_file:
    readme = readme_file.read()

with open("HISTORY.rst") as history_file:
    history = history_file.read()

requirements = []

setup_requirements = [
    "pytest-runner",
]

test_requirements = ["pytest>=3", 'dataclasses; python_version < "3.7"']

setup(
    author="Loic Leyendecker",
    author_email="loic.leyendecker@gmail.com",
    python_requires=">=3.6",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    description="Python module to easily manipulate complex nested structures",
    install_requires=requirements,
    license="MIT license",
    long_description=readme + "\n\n" + history,
    include_package_data=True,
    keywords="deeppath",
    name="deeppath",
    packages=find_packages(include=["deeppath", "deeppath.*"]),
    setup_requires=setup_requirements,
    test_suite="tests",
    tests_require=test_requirements,
    url="https://github.com/loicleyendecker/deeppath",
    version=__version__,
    zip_safe=False,
)
