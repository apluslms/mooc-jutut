from django.db import transaction
from django.core.management.base import BaseCommand, CommandError

from ...models import Form


def get_concrete_classes(cls):
    concrete = set()
    pool = set((cls,))
    while pool:
        current = pool.pop()
        if not current._meta.abstract and not current._meta.proxy:
            concrete.add(current)
        pool.update(current.__subclasses__())
    return concrete


class Command(BaseCommand):
    help = 'Recalculate hashsum for form specs. Required if hash calculation changes.'

    def handle(self, *args, **options):
        models = get_concrete_classes(Form)
        models_count = len(models)
        for model_n, model in enumerate(models, 1):
            items = model.objects.all()
            total = items.count()
            prefix = model.__name__
            if models_count > 1:
                prefix += "{}/{}".format(model_n, models_count)

            self.stdout.write(self.style.SUCCESS("Recalculating {} items for model {},".format(total, prefix)))

            for item_n, item in enumerate(items, 1):
                old = item.sha1
                item.sha1 = None
                item.save(update_fields=['sha1'])
                self.stdout.write(self.style.NOTICE("{}, item {}/{}: Updated {} to {}".format(prefix, item_n, total, old, item.sha1)))
