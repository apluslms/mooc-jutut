from django.views.generic.base import TemplateResponseMixin, View
from django.views.generic.edit import ModelFormMixin
from django.views.generic.list import MultipleObjectMixin


class ListCreateView(TemplateResponseMixin,
                     ModelFormMixin,      # CreateView
                     MultipleObjectMixin, # ListView
                     View):
    def get(self, request, *args, **kwargs):
        # BaseCreateView
        self.object = None
        # BaseListView, stripped. We presume allow_empty is True.
        self.object_list = self.get_queryset()
        return self.render_to_response(self.get_context_data())

    def post(self, request, *args, **kwargs):
        # BaseCreateView:
        self.object = None
        # ProcessFormView:
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        # BaseListView: - load objects before render_to_response
        self.object_list = self.get_queryset()
        return self.form_invalid(form)

    def get_context_object_name(self, object_list): # pylint: disable=arguments-renamed
        # reply None for SingleObjectMixin always
        # we presume we are in MultipleObjectMixin if argument has `model` member
        if not hasattr(object_list, 'model'):
            return None
        return super().get_context_object_name(object_list)
