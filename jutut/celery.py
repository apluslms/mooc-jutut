import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jutut.settings')


class JututCelery(Celery):
    def gen_task_name(self, name, module):
        if module.endswith('.tasks'):
            module = module[:-6]
        return super().gen_task_name(name, module)


# Initialize and load celery app
app = JututCelery('jutut')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))
