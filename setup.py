"""Packaging metadata for the trading platform.

Kept intentionally minimal; the platform is normally run from source or via
Docker rather than installed as a wheel.
"""
from pathlib import Path

from setuptools import find_packages, setup

_here = Path(__file__).parent
_long_desc = (_here / "README.md").read_text(encoding="utf-8") if (_here / "README.md").exists() else ""


def _read_requirements() -> list[str]:
    req = _here / "requirements.txt"
    if not req.exists():
        return []
    out = []
    for line in req.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("-"):
            out.append(line)
    return out


setup(
    name="autonomous-trading-platform",
    version="0.1.0",
    description="Autonomous Adaptive Trading Intelligence Platform (risk-first, paper-default).",
    long_description=_long_desc,
    long_description_content_type="text/markdown",
    python_requires=">=3.11",
    packages=find_packages(exclude=("tests", "tests.*")),
    install_requires=_read_requirements(),
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3.11",
        "Intended Audience :: Financial and Insurance Industry",
        "Topic :: Office/Business :: Financial :: Investment",
    ],
)
