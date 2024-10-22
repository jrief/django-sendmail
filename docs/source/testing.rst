Testing
===========

Tests are available on ``testapp`` branch in ``demoapp``. To run them simply you will have to install:

- pytest
- pytest-django
- pytest-mock
- pytest-cov

And open-source emails tests utility named `Mailpit <https://github.com/axllent/mailpit>`_, which is used for integration testing in the project.

To run tests suits simply enable mailpit with defaults configurations and execute ``pytest demoapp`` from the root directory.

