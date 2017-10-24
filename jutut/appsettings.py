from django_settingsdict import SettingsDict


app_settings = SettingsDict(
    'JUTUT',
    defaults={
        'TEXT_FIELD_MIN_LENGTH': 2,
    },
)
