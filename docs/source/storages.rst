Storages
===========


``sendmail`` supports integration with `django-storages <https://django-storages.readthedocs.io/en/latest/>`_. By default FileSystemStorage is used for storing sendmail data.
You can override this behaviour by specifying ``STORAGES`` config in ``settings.py``.

For example for configuring `MiniIO <https://github.com/minio/minio?tab=readme-ov-file>`_ (compatible with S3 API):

Install django-storages and boto3:

.. code-block::

    pip install django-storages boto3

To your installed apps add ``storages``

Define your storages:

.. code-block:: python

    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": {
                "endpoint_url": 'http://138.232.3.68:9000',  # Note the lowercase 'endpoint_url'
                'access_key': 'minioadmin',
                'secret_key': 'minioadmin',
                'bucket_name': 'media',
                'querystring_auth': False,
                'use_ssl': False,  # Set this to True if you use HTTPS
                'file_overwrite': False,  # Optional: set to False to avoid overwriting files with the same name
            },
        },
        'staticfiles': {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": {
                "endpoint_url": 'http://138.232.3.68:9000',  # Note the lowercase 'endpoint_url'
                'access_key': 'minioadmin',
                'secret_key': 'minioadmin',
                'bucket_name': 'static',
                'querystring_auth': False,
                'use_ssl': False,  # Set this to True if you use HTTPS
                'file_overwrite': False,  # Optional: set to False to avoid overwriting files with the same name
            },
        },
        'sendmail_attachments': {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": {
                "endpoint_url": 'http://138.232.3.68:9000',
                'access_key': 'minioadmin',
                'secret_key': 'minioadmin',
                'bucket_name': 'attachments',
                'querystring_auth': True,
                'use_ssl': False,
                'file_overwrite': False,
            }
        }
    }

- ``default`` storage is used to store ``mediafiles``.
  In context of ``boto3`` it should always have ``querystring_auth = False``. To ensure proper work of ``ckeditor_uploader``.

- ``staticfiles`` storage is used to store project ``staticfiles``.
  As project depends on ``ckeditor`` it should always have ``querystring_auth = False``.

- ``sendmail_attachments`` storage used to store ckeditor attachments. Defaults to ``default_storage``.
  **Strongly recommended to override it with any private storage.**

