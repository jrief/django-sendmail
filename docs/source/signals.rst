Signals
============

Each time an email is added to the mail queue, Sendmail emits a special `Django signal <https://docs.djangoproject.com/en/5.1/topics/signals/>`_.
Whenever a third party application wants to be informed about this event,
it shall connect a callback function to the Sendmail signal handler ``email_queued``, for instance:

.. code-block:: python

    from django.dispatch import receiver
    from sendmail.signals import email_queued

    @receiver(email_queued)
    def my_callback(sender, emails, **kwargs):
        print("Added {} mails to the sending queue".format(len(emails)))

The Emails objects added to the queue are passed as list to the callback handler.

**Note** when you use :ref:`mail.send_many()` you will get emails batch by batch.

If you are using :ref:`Email Tracking` feature and want to extend the behavior of 
email open and click views you can connect to ``email_opened`` and ``email_clicked`` signals.

For example to save the latest opened and clicked timestamps instead of first ones:

.. code-block:: python

    from django.dispatch import receiver
    from sendmail.signals import email_opened, email_clicked
    from django.utils import timezone
    
    @receiver(email_opened)
    def change_opened_at(sender, email, **kwargs):
        email.opened_at = timezone.now()
        email.save()
        
    @receiver(email_clicked)
    def change_clicked_at(sender, email, **kwargs):
        email.clicked_at = timezone.now()
        email.save()

