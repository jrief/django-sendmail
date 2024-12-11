from django.dispatch import Signal

email_queued = Signal()
"""
This signal is triggered whenever Sendmail pushes one or more emails into its queue.
The Emails objects added to the queue are passed as list to the callback handler.
It can be connected to any handler function using this signature:

Example:
    from django.dispatch import receiver
    from sendmail.signal import email_queued

    @receiver(email_queued)
    def my_callback(sender, emails, **kwargs):
        print("Just added {} mails to the sending queue".format(len(emails)))
"""

email_opened = Signal()
email_clicked = Signal()
"""
These signals are triggered whenever Sendmail receives an email opened or clicked event respectively.
The email object is passed to the callback handler.
It can be connected to any handler function using this signature:

@receiver(email_opened)
def my_callback(sender, email, **kwargs):
    print(f"Email {email} opened")

@receiver(email_clicked)
def my_callback(sender, email, **kwargs):
    print(f"Email {email} clicked")

"""


