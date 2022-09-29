from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class CheckPermissionsMixin(LoginRequiredMixin, UserPassesTestMixin):
    permission_classes = []

    def get_permissions(self):
        return [Permission() for Permission in self.permission_classes]

    def test_func(self):
        """
        Tested by UserPassesTestMixin
        """
        request = self.request
        permissions = self.get_permissions()
        if not permissions:
            raise RuntimeError("View {} doesn't have any permissions defined".format(self.__class__.__name__))
        for permission in permissions:
            if not permission.has_permission(request, self):
                return False
        return True


class Permission:
    def has_permission(self, request, _view):
        return True
