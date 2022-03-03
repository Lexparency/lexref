from setuptools import setup


setup(
    name="lexref",
    author="Martin Heimsoth",
    author_email="mail@lexparency.org",
    url="https://github.com/Lexparency/lexref",
    description="",
    version="1.1",
    packages=['lexref'],
    package_data={
        '': ['static/named_entity.csv'],
    },
    install_requires=['anytree', 'lxml'],
)
