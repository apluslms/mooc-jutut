try:
    import django
except ImportError as exc:
    raise ImportError("aplus_client.django requires django and is only useful with it") from exc

default_app_config = 'aplus_client.django.apps.AplusClientConfig'
