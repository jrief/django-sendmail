# Generated by Django 5.1 on 2024-10-09 11:49

import django.db.models.deletion
import sendmail.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sendmail', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailMergeContentModel',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('language', models.CharField(max_length=12)),
                ('subject', models.CharField(blank=True, max_length=255, validators=[sendmail.validators.validate_template_syntax], verbose_name='Subject')),
                ('content', models.TextField(blank=True, validators=[sendmail.validators.validate_template_syntax], verbose_name='Content')),
            ],
            options={
                'verbose_name': 'Email Template Content',
                'verbose_name_plural': 'Email Template Contents',
            },
        ),
        migrations.RemoveConstraint(
            model_name='emailmergemodel',
            name='unique_emailmerge',
        ),
        migrations.RemoveField(
            model_name='emailmergemodel',
            name='content',
        ),
        migrations.RemoveField(
            model_name='emailmergemodel',
            name='default_template',
        ),
        migrations.RemoveField(
            model_name='emailmergemodel',
            name='language',
        ),
        migrations.RemoveField(
            model_name='emailmergemodel',
            name='subject',
        ),
        migrations.AddField(
            model_name='emailmodel',
            name='language',
            field=models.CharField(default='en', max_length=12),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='emailmergemodel',
            name='name',
            field=models.CharField(help_text="e.g: 'welcome_email'", max_length=255, unique=True, verbose_name='Name'),
        ),
        migrations.AddField(
            model_name='emailmergecontentmodel',
            name='emailmerge',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='translated_contents', to='sendmail.emailmergemodel'),
        ),
        migrations.AddConstraint(
            model_name='emailmergecontentmodel',
            constraint=models.UniqueConstraint(fields=('emailmerge', 'language'), name='unique_content'),
        ),
    ]
