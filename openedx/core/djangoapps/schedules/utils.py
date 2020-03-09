

import datetime
import logging

import pytz

from openedx.core.djangoapps.schedules.models import Schedule

LOG = logging.getLogger(__name__)


# TODO: consider using a LoggerAdapter instead of this mixin:
# https://docs.python.org/2/library/logging.html#logging.LoggerAdapter
class PrefixedDebugLoggerMixin(object):
    log_prefix = None

    def __init__(self, *args, **kwargs):
        super(PrefixedDebugLoggerMixin, self).__init__(*args, **kwargs)
        if self.log_prefix is None:
            self.log_prefix = self.__class__.__name__

    def log_debug(self, message, *args, **kwargs):
        """
        Wrapper around LOG.debug that prefixes the message.
        """
        LOG.debug(self.log_prefix + ': ' + message, *args, **kwargs)

    def log_info(self, message, *args, **kwargs):
        """
        Wrapper around LOG.info that prefixes the message.
        """
        LOG.info(self.log_prefix + ': ' + message, *args, **kwargs)


def reset_self_paced_schedule(user, course_key):
    """
    Reset the user's schedule if self-paced, to the current time.

    It does not create a new schedule, just resets an existing one.
    This is used, for example, when a user requests it or when an enrollment mode changes.
    """
    Schedule.objects.filter(
        enrollment__user=user,
        enrollment__course__id=course_key,
        enrollment__course__self_paced=True,
    ).update(start_date=datetime.datetime.now(pytz.utc))
