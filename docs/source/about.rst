About SendMail
===================


``django-sendmail`` is a fork of the excellent `django-post-office <https://github.com/ui/django-post_office>`_, a powerful Django app for asynchronous email sending.

The creation of this fork was driven by a desire to introduce additional features and improvements while building on the solid foundation provided by django-post-office. Key enhancements include:

- Using database locking instead of file-based locking to better support distributed environments.

- Introducing a two-phase templating system to eliminate the need for direct HTML coding in the admin panel.

- Enabling recipient-specific context for personalized emails.

- Improving performance in Celery-enabled environments.

- Providing seamless integration with various storage backends.

- These changes aim to extend the functionality of the original project while preserving its core strengths.