from setuptools import setup, find_packages
import pathlib

here = pathlib.Path(__file__).parent.resolve()

# Get the long description from the README file
long_description = (here / 'README.md').read_text(encoding='utf-8')

setup(
    name="synrad-uc2000-TobyBi",
    version="2021.03",
    description="Wrapper for SYNRAD UC2000 Controller",
    long_description=long_description,
    long_description_content_type='text/markdown',
    url="https://github.com/TobyBi/synrad_uc2000",
    author="Toby Bi",
    author_email="toby.bi@outlook.com",
    packages=find_packages(where="src",),
    python_requires=">=3.8, <4",
    install_requires=[]
)