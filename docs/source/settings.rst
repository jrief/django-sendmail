Settings
============

This section outlines all the settings and configurations that you can put in Django's ``settings.py`` to fine tune ``sendmail``'s behavior.

Batch Size
-------------

This setting is used to limit the number of emails sent in a batch.
This is useful to control :ref:`mail.send_many()` in multiprocessing environment
(in this context it sets the maximum number of emails handled by one process).
You may want to adjust it to maximize the performance, taking into account your setup and expected load.
Defaults to ``100``.

.. code-block:: python

    SENDMAIL = {
    ...
    'BATCH_SIZE': 100,
    }

There is also a companion setting called ``BATCH_DELIVERY_TIMEOUT``.
This setting specifies the maximum time allowed for each batch to be delivered,
this is useful to guard against cases where delivery process never terminates.
Defaults to ``180``.

If you send a large number of emails in a single batch on a slow connection, consider increasing this number.

.. code-block:: python

    SENDMAIL = {
        ...
        'BATCH_DELIVERY_TIMEOUT': 180,
    }

Default Priority
------------------

The default priority for emails is ``medium``, but this can be altered by setting ``DEFAULT_PRIORITY``.
Integration with asynchronous email backends (e.g. based on Celery) becomes trivial when set to ``now``.

.. code-block:: python

    SENDMAIL = {
    ...
    'DEFAULT_PRIORITY': 'now',
    }

Message-ID
--------------

The SMTP standard requires that each email contains a unique `Message-ID <https://datatracker.ietf.org/doc/html/rfc2822#section-3.6.4>`_.
Typically the Message-ID consists of two parts separated by the ``@`` symbol: The left part is a generated pseudo random number.
The right part is a constant string, typically denoting the full qualified domain name of the sending server.

By default, **Django** generates such a Message-ID during email delivery. Since ``django-sendmail`` keeps track of all delivered emails, it can be very useful to create and store this Message-ID while creating each email in the database. This identifier then can be looked up in the Django admin backend.

To enable this feature, add this to your sendmail settings:

.. code-block:: python

    SENDMAIL = {
    ...
    'MESSAGE_ID_ENABLED': True,
    }

It can further be fine tuned, using for instance another full qualified domain name:

.. code-block:: python

    SENDMAIL = {
        ...
        'MESSAGE_ID_ENABLED': True,
        'MESSAGE_ID_FQDN': 'example.com',
    }

Otherwise, if ``MESSAGE_ID_FQDN`` is unset (the default), ``django-sendmail`` falls back to the DNS name of the server,
which is determined by the network settings of the host.

Retry
--------

Not activated by default. You can automatically requeue failed email deliveries.
You can also configure failed deliveries to be retried after a specific time interval.

.. code-block:: python

    SENDMAIL = {
        ...
        'MAX_RETRIES': 4,
        'RETRY_INTERVAL': datetime.timedelta(minutes=15),  # Schedule to be retried 15 minutes later
    }

Log Level
---------------

Logs are stored in the database and is browsable via Django admin. The default log level is 2 (logs both successful and failed deliveries)
This behavior can be changed by setting ``LOG_LEVEL``.

.. code-block:: python

    SENDMAIL = {
        ...
        'LOG_LEVEL': 1, # Log only failed deliveries
    }

The different options are:

- ``0`` logs nothing
- ``1`` logs only failed deliveries
- ``2`` logs everything (both successful and failed delivery attempts)

Sending Order
---------------

The default sending order for emails is ``-priority``, but this can be altered by setting SENDING_ORDER.
For example, if you want to send queued emails in FIFO order :

.. code-block:: python

    SENDMAIL = {
        ...
        'SENDING_ORDER': ['created'],
    }

Logging
------------

You can configure ``sendmail``'s logging from Django's ``settings.py``. For example:

.. code-block:: python

    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "sendmail": {
                "format": "[%(levelname)s]%(asctime)s PID %(process)d: %(message)s",
                "datefmt": "%d-%m-%Y %H:%M:%S",
            },
        },
        "handlers": {
            "sendmail": {
                "level": "DEBUG",
                "class": "logging.StreamHandler",
                "formatter": "sendmail"
            },
            # If you use sentry for logging
            'sentry': {
                'level': 'ERROR',
                'class': 'raven.contrib.django.handlers.SentryHandler',
            },
        },
        'loggers': {
            "sendmail": {
                "handlers": ["sendmail", "sentry"],
                "level": "INFO"
            },
        },
    }

CKEDITOR Config
------------------

You may want to adjust `django-ckeditor <https://django-ckeditor.readthedocs.io/en/latest/>`_ default config to provide
more (or less) editing options for 2-phase template editors. For this simply add to your ``settings.py`` desired config:

.. code-block:: python

    CKEDITOR_CONFIGS = {
    'default': {
        'toolbar': 'Custom',
        'toolbar_Custom': [
            ['Bold', 'Italic', 'Underline'],
            ['NumberedList', 'BulletedList', '-', 'Outdent', 'Indent', '-', 'JustifyLeft', 'JustifyCenter',
             'JustifyRight', 'JustifyBlock'],
            ['Link', 'Unlink'],
            ['Image'],
            ['Format']  # Adding headers (e.g., Heading 1, Heading 2, etc.)
        ],
        'format_tags': 'p;h1;h2;h3;pre',  # Define the available formats (headers and others)
        'width': 1000
        }
    }

Adjust this to meet your needs.

.. warning::
    Edited content is cleaned before rendering in email templates to avoid XSS vulnerabilities.
    However it is still not recommended to have buttons like ``Source`` in your config.

