from django.db import transaction
from django.db import connection as db_connection
from django.tasks import task

from sendmail.mail import get_queued, _send_bulk


def queued_mail_handler(sender, **kwargs):
    """
    Trigger an asynchronous mail delivery.
    """
    send_queued_mail.enqueue()


@task
def send_queued_mail(*args, **kwargs):
    """
    To be called by the Celery task manager.
    """

    while True:
        queued_emails = get_queued().select_for_update(of=('self',), skip_locked=True)
        with transaction.atomic():
            try:
                _send_bulk(queued_emails, uses_multiprocessing=False)
            except Exception as e:
                raise e

            if not get_queued().select_for_update(of=('self',), skip_locked=True).exists():
                break
        db_connection.close()
