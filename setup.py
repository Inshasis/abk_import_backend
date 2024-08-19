from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in sales_application_plugin/__init__.py
from sales_application_plugin import __version__ as version

setup(
	name="sales_application_plugin",
	version=version,
	description="Sales Application backend",
	author="Akhilam INC",
	author_email="raaj@akhilaminc.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
