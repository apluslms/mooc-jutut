# Hstore Aggregates
from django.db.models.aggregates import Aggregate, Avg
from django.contrib.postgres import fields


class PgAggregate(Aggregate):
    """
    Aggergation superclass for postgre specifig HStore, Json and Jsonb fields.
    """
    template = "%(function)s((%(field)s %(get_field_oper)s '%(key)s')::%(data_type)s)"

    def __init__(self, field, key=None, data_type=None, get_field_oper=None, **kwargs):
        if not key:
            field, key = field.split('->', 1)
        self.__data_type = data_type
        self.__get_field_oper = get_field_oper
        super(PgAggregate, self).__init__(field.strip(), key=key.strip(), **kwargs)

    def resolve_expression(self, *args, **kwargs):
        resolved = super().resolve_expression(*args, **kwargs)
        field_class = type(resolved.get_source_expressions()[0].target)
        if field_class in [fields.jsonb.JSONField]:
            data_type = self.__data_type or 'numeric'
            get_field_oper = self.__get_field_oper or '->>'
        elif field_class in [fields.jstore.HStoreField]:
            data_type = self.__data_type or 'integer'
            get_field_oper = self.__get_field_oper or '->'
        resolved.extra['data_type'] = data_type
        resolved.extra['get_field_oper'] = get_field_oper
        return resolved

class PgAvg(PgAggregate):
    function = "AVG"

class PgSum(PgAggregate):
    function = "SUM"

class PgMin(PgAggregate):
    function = "MIN"

class PgMax(PgAggregate):
    function = "MAX"
