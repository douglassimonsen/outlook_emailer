import setuptools


setuptools.setup(
    name="outlook_emailer",
    packages=['outlook_emailer'],
    version="1.0.0",
    description="A package that provides a simple way of sending emails through Microsoft Exchange",
    url="https://github.com/<email_addr>/outlook_emailer",
    download_url="https://github.com/<email_addr>/outlook_emailer/archive/1.0.0.tar.gz",
    author="Matthew Hamilton",
    author_email="<email_addr>@gmail.com",
    license="MIT",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
    ],
    include_package_data=True,
    install_requires=[
        "colorsys",
        "openpyxl",
        "jinja2",
    ],
)
