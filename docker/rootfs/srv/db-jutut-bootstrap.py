# pylint: disable=import-outside-toplevel

import os
import sys
import django


def create_default_users():
    from accounts.models import JututUser as User

    u1 = User.objects.create(
        username="root",
        email="root@localhost",
        first_name="Ruth",
        last_name="Robinson",
        is_superuser=True,
        is_staff=True,
    )
    u1.set_password("root")
    u1.save()


if __name__ == '__main__':
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jutut.settings")
    sys.path.insert(0, '')
    django.setup()

    create_default_users()
