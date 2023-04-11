from ansi2html import Ansi2HTMLConverter
from collections import OrderedDict
from django.core.cache import cache
from django.views.generic import TemplateView

from jutut.appsettings import app_settings

from .permissions import LoginRequiredMixin
from .utils import check_system_service_status


class ServiceStatusPage(LoginRequiredMixin, TemplateView):
    template_name = "core/statuspage.html"


class ServiceStatusData(LoginRequiredMixin, TemplateView):
    template_name = "core/statuspage_data.html"

    def get_context_data(self, **kwargs): # pylint: disable=too-many-locals
        context = super().get_context_data()

        from feedback.forms_dynamic import DynamicFeedbacForm # pylint: disable=import-outside-toplevel
        context['dynamic_form_cache_size'] = len(DynamicFeedbacForm.FORM_CACHE)
        context['dynamic_form_cache_max'] = DynamicFeedbacForm.FORM_CACHE.max_size

        from jutut.celery import app # pylint: disable=import-outside-toplevel
        i = app.control.inspect()
        context['celery_stats'] = celery_stats = {}
        for group in ('active', 'scheduled', 'reserved'):
            for host, items in (getattr(i, group)() or {}).items():
                if host not in celery_stats:
                    celery_stats[host] = {}
                celery_stats[host][group] = len(items)
        for host, stats in i.stats().items():
            if host not in celery_stats:
                celery_stats[host] = {}
            celery_stats[host]['total'] = total_tasks = stats['total']
            total_done = max(sum(total_tasks.values()), 1)
            celery_stats[host]['processes'] = len(stats['pool']['processes'])
            utime = stats['rusage']['utime']
            stime = stats['rusage']['stime']
            celery_stats[host]['time'] = {
                'utime': utime,
                'stime': stime,
                'sutime': utime/total_done,
                'sstime': stime/total_done,
            }

        context['celery_totals'] = celery_totals = {}
        for host, data in celery_stats.items():
            for key, value in data.items():
                if isinstance(value, dict):
                    if key not in celery_totals:
                        celery_totals[key] = OrderedDict()
                    d = celery_totals[key]
                    for subkey, subvalue in value.items():
                        if subkey not in d:
                            d[subkey] = subvalue
                        else:
                            d[subkey] += subvalue
                else:
                    if key not in celery_totals:
                        celery_totals[key] = value
                    else:
                        celery_totals[key] += value

        context['service_status'] = service_status = OrderedDict()
        ansi2html = Ansi2HTMLConverter()
        a2h = lambda x: ansi2html.convert(x, full=False) # pylint: disable=unnecessary-lambda-assignment
        for name, command in app_settings.SERVICE_STATUS:
            ok, out = check_system_service_status(command)
            service_status[name] = {
                'cmd': command if isinstance(command, str) else ' '.join(command),
                'ok': ok,
                'out': a2h(out) if out else None,
            }

        return context


class ClearCache(LoginRequiredMixin, TemplateView):
    template_name = "core/cache_cleared.html"

    def get(self, *args, **kwargs):
        cache.clear()
        return super().get(*args, **kwargs)
