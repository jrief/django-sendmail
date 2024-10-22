Signals
============

Each time an email is added to the mail queue, Post Office emits a special `Django signal <https://docs.djangoproject.com/en/5.1/topics/signals/>`_.
Whenever a third party application wants to be informed about this event,
it shall connect a callback function to the Post Office's signal handler ``email_queued``, for instance:

.. code-block:: python

    from django.dispatch import receiver
    from sendmail.signals import email_queued

    @receiver(email_queued)
    def my_callback(sender, emails, **kwargs):
        print("Added {} mails to the sending queue".format(len(emails)))

The Emails objects added to the queue are passed as list to the callback handler.

**Note** when you use :ref:`mail.send_many()` you will get emails batch by batch.



