from ast import literal_eval
from os.path import dirname, join

from setuptools import find_packages, setup

with open(join(dirname(__file__), 'sendmail/version.txt'), 'r') as fh:
    VERSION = '.'.join(map(str, literal_eval(fh.read())))

setup(
    name='django-sendmail',
    version=VERSION,
    author='Mykhailo Poienko, Jacob Rief',
    author_email='22IMC10258@fh-krems.ac.at',
    packages=find_packages(exclude=['demoapp', 'demoapp.tests', 'demoapp.custom_user', 'demoapp.custom_user.migrations']),
    url='https://github.com/jrief/django-sendmail',
    license='MIT',
    description='A Django app to monitor and send mail asynchronously, complete with template support.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    zip_safe=False,
    include_package_data=True,
    package_data={'': ['README.md']},
    install_requires=['Django>=4.0', 'django-ckeditor>=6.0', 'lxml>=5.0', 'nh3>=0.2'],
    extras_require={
        'jsoneditor': ['django-jsoneditor>=0.2.0']
    },
    keywords=[
        'django', 'email', 'sendmail', 'template', 'async', 'celery'
    ],
    project_urls={
        'Documentation': 'https://django-sendmail.readthedocs.io/en/latest/',
        'Source': 'https://github.com/jrief/django-sendmail'
    },
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
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Topic :: Communications :: Email',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]
)
