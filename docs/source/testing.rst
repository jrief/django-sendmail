Testing
===========

Tests are available in ``demoapp`` sample project. To run them you will have to install:

- pytest
- pytest-django
- pytest-mock
- pytest-cov

And open-source emails tests utility named `Mailpit <https://github.com/axllent/mailpit>`_, which is used for integration testing in the project.

To run tests suits simply enable ``mailpit`` or export your ``MAILPIT_BINARY`` path to environmental variables and execute ``pytest demoapp`` from the root directory.

