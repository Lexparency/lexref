from setuptools import setup


setup(
    name="lexref",
    author="Martin Heimsoth",
    author_email="martin.heimsoth@lexparency.org",
    url="https://reflex.lexparency.org",
    version="1.0",
    packages=['lexref'],
    package_data={
        '': ['static/named_entity.csv'],
    },
    install_requires=['anytree', 'lxml'],
)
