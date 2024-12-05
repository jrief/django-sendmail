from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PostOfficeConfig(AppConfig):
    name = 'sendmail'
    verbose_name = _('SendMail')
    default_auto_field = 'django.db.models.AutoField'
    default_settings = {
        'BATCH_SIZE': 100,
    }

    def ready(self):
        import sendmail.checks  # noqa: F401
        from sendmail import tasks
        from sendmail.settings import get_celery_enabled
        from sendmail.signals import email_queued

        if get_celery_enabled():
            email_queued.connect(tasks.queued_mail_handler)
