# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-04-08 13:36
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('push', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='digestsubscription',
            name='endpoint',
            field=models.CharField(editable=False, max_length=512, unique=True, verbose_name='endpoint'),
        ),
    ]
