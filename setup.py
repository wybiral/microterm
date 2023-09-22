import setuptools

with open('README.md', 'r') as f:
    long_description = f.read()

setuptools.setup(
    name='microterm',
    version='0.1.0',
    author='davy wybiral',
    author_email="davy.wybiral@gmail.com",
    description='CLI tool for interacting with MicroPython devices',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/wybiral/microterm",
    packages=['microterm'],
    install_requires=['pyserial'],
    license='MIT',
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
