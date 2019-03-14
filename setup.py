# -*- coding: utf-8 -*-
import os

from setuptools import setup


README = open(os.path.join(os.path.dirname(__file__), 'README.rst')).read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))


setup(
    name='django_infopush',
    version='1.6.5',
    packages=['push'],
    include_package_data=True,
    license='WTFPL License',
    description='Django reusable app, what allows to send web push.',
    long_description=README,
    # url='http://gurutest.ru/',
    author='Yuriy Zemskov',
    author_email='zemskyura@gmail.com',
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    ],
    install_requires=[
        'Django>=1.11.9,<2.0',
        'django-commonstuff>=0.8.6',
        'pytz>=2018.3',
        'Pillow>=4.3.0',  # for dimensions on image upload
        'pywebpush==1.7.0',  # payload encryption
    ]
)

