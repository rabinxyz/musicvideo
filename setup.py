from setuptools import setup, find_packages

setup(
    name="musicvid",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        line.strip()
        for line in open("musicvid/requirements.txt")
        if line.strip() and not line.startswith("#")
    ],
    entry_points={
        "console_scripts": [
            "musicvid=musicvid.musicvid:cli",
        ],
    },
)
