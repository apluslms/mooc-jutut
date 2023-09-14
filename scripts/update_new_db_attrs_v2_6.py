"""In the version upgrade v2.6, new fields were added to the database tables.
Some tables must be updated manually afterwards so that
existing records are updated with the correct values for the new attributes.
This script fills in the missing attributes for exercises.
"""
import argparse
import os
import sys
import time
from os.path import abspath, dirname

from django.db.models import Q


def update_exercise_attrs(api_token):
    from aplus_client.client import AplusTokenClient # pylint: disable=import-outside-toplevel
    from feedback.models import Exercise # pylint: disable=import-outside-toplevel

    client = AplusTokenClient(api_token, version=2)

    all_exercises = Exercise.objects.filter(Q(parent_name='') | Q(consecutive_order=0))
    for exercise in all_exercises:
        try:
            exercise_json = client.load_data(f"{exercise.url}?format=json")
            if exercise_json.parent_name and exercise.parent_name == '':
                exercise.parent_name = exercise_json.parent_name
            if exercise_json.consecutive_order and exercise.consecutive_order == 0:
                exercise.consecutive_order = exercise_json.consecutive_order
            exercise.save()
        except Exception as exc:
            print(f"ERROR in downloading exercise data: api_id={exercise.api_id} | {exercise.url}")
            print(exc)

        time.sleep(1)


if __name__ == '__main__':
    sys.path.append(dirname(dirname(abspath(__file__))))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jutut.settings")
    import django
    django.setup()

    parser = argparse.ArgumentParser(
        description="Fix the missing (empty) exercise attributes in the exercises "
                    "that existed before the Jutut version upgrade v2.6",
    )
    parser.add_argument("api_token",
                        help="A+ API token for a user that has access "
                             "to all of the targeted courses.",)

    args = parser.parse_args()

    update_exercise_attrs(args.api_token)
