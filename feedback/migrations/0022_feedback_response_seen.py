# Generated by Django 4.2.11 on 2024-05-13 18:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("feedback", "0021_contexttag"),
    ]

    operations = [
        migrations.AddField(
            model_name="feedback",
            name="response_seen",
            field=models.BooleanField(default=False, null=True),
        ),
    ]
