from ast import literal_eval
import sys
from os.path import dirname, join
from setuptools import setup
from setuptools.command.test import test as TestCommand

with open(join(dirname(__file__), 'sendmail/version.txt'), 'r') as fh:
    VERSION = '.'.join(map(str, literal_eval(fh.read())))

setup(
    name='django-sendmail',
    version=VERSION,
    author='Mykhailo Poienko, Jacob Rief',
    author_email='22IMC10258@fh-krems.ac.at',
    packages=['sendmail'],
    url='https://github.com/jrief/django-sendmail',
    license='MIT',
    description='A Django app to monitor and send mail asynchronously, complete with template support.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    zip_safe=False,
    include_package_data=True,
    package_data={'': ['README.md']},
    install_requires=['django>=4.0', ],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Topic :: Communications :: Email',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]
)
