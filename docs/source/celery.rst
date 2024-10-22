Integration with Celery
===============================

If your project runs in a Celery enabled environment, you can use its worker to send out queued emails.
This setup has a big advantage that emails are sent immediately after they are added to the queue.
The delivery is performed asynchronously in a separate task to prevent blocking request/response-cycle.

.. warning::
    Current version of sendmail uses Django ORM ``select_for_update(skip_locked=True)`` method in celery task
    for locking sent emails. Not all database backends support it.

    "Using select_for_update() on backends which do not support SELECT ... FOR UPDATE (such as SQLite) will have no effect.
    SELECT ... FOR UPDATE will not be added to the query, and an error isn’t raised if select_for_update() is used in autocommit mode."
    (read more in `Django QuerySet documentation <https://docs.djangoproject.com/en/5.1/ref/models/querysets/>`_)

You should `configure celery <https://docs.celeryq.dev/en/latest/userguide/application.html>`_ so that you ``celery.py``
setup invokes `autodiscover_tasks <https://docs.celeryq.dev/en/latest/reference/celery.html#celery.Celery.autodiscover_tasks>`_

Celery must also be enabled in sendmail configurations in ``settings.py``:

.. code-block:: python

    SENDMAIL = {
    # other settings
    'CELERY_ENABLED': True,
    }

Now you can start celery worker:

.. code-block::

    python -m celery -A your_project worker -l info --concurrency=5

Adjust number of concurrent processes to meet your needs.

You should see something like this:

.. code-block::

         -------------- celery@mykhailo-Latitude-5540 v5.4.0 (opalescent)
    --- ***** -----
    -- ******* ---- Linux-6.8.0-45-generic-x86_64-with-glibc2.39 2024-10-08 13:36:49
    - *** --- * ---
    - ** ---------- [config]
    - ** ---------- .> app:         celery_project:0x7e00fa50c710
    - ** ---------- .> transport:   redis://localhost:6379//
    - ** ---------- .> results:     redis://localhost:6379/
    - *** --- * --- .> concurrency: 5 (prefork)
    -- ******* ---- .> task events: OFF (enable -E to monitor tasks in this worker)
    --- ***** -----
     -------------- [queues]
                    .> celery           exchange=celery(direct) key=celery


    [tasks]
      . sendmail.tasks.cleanup_mail
      . sendmail.tasks.send_queued_mail

In case of a temporary delivery failure, we might want retrying to send those emails by a periodic task.
This can be scheduled with a simple `Celery beat configuration <https://docs.celeryq.dev/en/latest/userguide/periodic-tasks.html#entries>`_,
for instance through

.. code-block:: python

    app.conf.beat_schedule = {
    'send-queued-mail': {
        'task': 'sendmail.tasks.send_queued_mail',
        'schedule': 600.0,
        },
    }

The email queue now will be processed every 10 minutes.
If you are using `Django Celery Beat <https://django-celery-beat.readthedocs.io/en/latest/>`_, then use the Django-Admin backend and add a periodic tasks for ``sendmail.tasks.send_queued_mail``.

Depending on your policy, you may also want to remove expired emails from the queue.
This can be done by adding another periodic tasks for ``sendmail.tasks.cleanup_mail``, which may run once a week or month.
