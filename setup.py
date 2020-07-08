# -*- coding: utf-8 -*-
import os
import setuptools


README = open(os.path.join(os.path.dirname(__file__), 'README.rst')).read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))


setuptools.setup(
    name='django_infopush',
    version='1.7.9',
    packages=setuptools.find_packages(),  # ['push'],
    include_package_data=True,
    license='MIT',
    description='Django reusable app, what allows to send web push.',
    long_description=README,
    long_description_content_type="text/x-rst",
    keywords='push webpush notifications fcm gcm vapid django reusable application app',
    author='Yuriy Zemskov',
    author_email='zemskyura@gmail.com',
    url='https://github.com/kilgoretrout1985/django_infopush',
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Django',
        'Framework :: Django :: 1.11',
        'Framework :: Django :: 2.2',
        'Framework :: Django :: 3.0',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    ],
    install_requires=[
        'Django>=1.11,<3.1',
        'django-commonstuff>=0.8.10',
        'pytz>=2020.1',
        'Pillow>=4.3.0',  # for dimensions on image upload
        'pywebpush>=1.9.3',  # payload encryption
        # for simultaneous support of Django 1.11 on Python 2.7 and Django 3.0
        # remove six dependency as soon as Django 1.11 and Python 2.7 both end
        # their lifecycle
        'six>=1.12.0',
    ]
)
