Integration with uWSGI
================================

If setting up Celery is too daunting and you use `uWSGI <https://uwsgi-docs.readthedocs.io/en/latest/>`_ as application server,
then uWSGI decorators can act as a poor men's scheduler.
Just add this short snipped to the project's ``wsgi.py`` file:

.. code-block:: python

    from django.core.wsgi import get_wsgi_application

    application = get_wsgi_application()

    # add this block of code
    try:
        import uwsgidecorators
        from django.core.management import call_command

        @uwsgidecorators.timer(10)
        def send_queued_mail(num):
            """Send queued mail every 10 seconds"""
            call_command('send_queued_mail', processes=1)

    except ImportError:
        print("uwsgidecorators not found. Cron and timers are disabled")

Alternatively you can also use the decorator ``@uwsgidecorators.cron(minute, hour, day, month, weekday)``.
This will schedule a task at specific times. Use ``-1`` to signal any time, it corresponds to the ``*`` in cron.

Please note that ``uwsgidecorators`` are available only, if the application has been started with uWSGI.
However, Django's internal ``./manange.py runserver`` also access this file, therefore wrap the block into an exception handler as shown above.

This configuration can be useful in environments, such as Docker containers, where you don't have a running cron-daemon.
