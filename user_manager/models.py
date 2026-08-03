from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

from . import custom_settings

# The host project supplies the abstract base class, so it can add its own fields and methods;
# user_manager turns it into the concrete, swappable User model. The default path is the one
# older versions hard-coded — new projects can point USER_MANAGER_ABSTRACT_USER_MODEL anywhere.
_base_path = custom_settings.USER_MANAGER_ABSTRACT_USER_MODEL

try:
    AbstractCustomUser = import_string(_base_path)
except ImportError as exc:
    raise ImproperlyConfigured(
        f"USER_MANAGER_ABSTRACT_USER_MODEL is {_base_path!r}, which could not be imported. "
        f"Define an abstract user model there, or set USER_MANAGER_ABSTRACT_USER_MODEL to the "
        f"dotted path of your own."
    ) from exc


class User(AbstractCustomUser):
    pass
