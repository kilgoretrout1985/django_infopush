django-infopush stores push endpoint urls in a unique varchar db-column. It was
255 chars length, but some endpoints (like ucbrowser or WNS) just don't fit to
255. The length of the field had to be increased. And that brings some problems
for MySQL users.

**If you use MySQL in your project, additional setup is required:**

1. Add the following line to your project's settings.py::

    SILENCED_SYSTEM_CHECKS = ['mysql.E001']

2. Check that your MySQL server version is 5.7.7 or greater.

    mysql> SELECT VERSION();

3. (OPTIONAL) If it is less than 5.7.7 `innodb_large_prefix` has to be
   activated in MySQL conf.

More information on the subject can be found
`here <https://stackoverflow.com/questions/45233362/django-says-that-mysql-does-not-allow-unique-charfields-to-have-a-max-length-2>`_.
