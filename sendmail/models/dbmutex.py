from django.db import models

from sendmail.logutils import setup_loghandlers

logger = setup_loghandlers('INFO')


class DBMutex(models.Model):
    """
    Model to store Database Locks.
    """
    lock_id = models.CharField(
        max_length=50,
        unique=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    expires_at = models.DateTimeField()

    locked_by = models.UUIDField(
        db_index=True,
    )

    def __str__(self):
        return f"<DBMutex(pk={self.pk}, lock_id={self.lock_id}>"

    class Meta:
        app_label = 'sendmail'

