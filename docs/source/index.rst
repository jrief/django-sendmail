.. post_office documentation master file, created by
   sphinx-quickstart on Wed Oct  2 15:24:50 2024.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

sendmail documentation
=========================

**Asynchronous email sending library for Django with enhanced templating options.**

sendmail provides a set of powerful features, such as:

- Handling millions of emails efficiently.
- Allows you to send emails asynchronously.
- Multi backend support.
- Support for inlined images.
- 2-phase email templating to allow non-technical users contributing to emails creation.
- Scheduling support.
- Works with task queues like RQ and Celery.
- Uses multiprocessing to send emails in parallel.
- Support of different storages.


.. toctree::
   :maxdepth: 2
   :caption: Contents:
   :numbered:

   dependencies
   installation
   quickstart
   usage
   settings
   storages
   celery
   uwsgi
   signals
   testing


