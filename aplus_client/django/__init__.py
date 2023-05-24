try:
    import django
except ImportError as exc:
    raise ImportError("aplus_client.django requires django and is only useful with it") from exc
