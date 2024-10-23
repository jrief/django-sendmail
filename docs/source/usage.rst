Usage
=========================

mail.send()
-----------

``mail.send()`` is one of the most important function in this library.
It is used to send **one** email to a list of recipients. It takes these arguments:

.. list-table:: mail.send() arguments
    :widths: 25 50 25 100
    :header-rows: 1

    * - Argument
      - Type
      - Required
      - Description
    * - recipients
      - str | List[str | EmailAddress]
      - Yes
      - List of recipient email addresses
    * - sender
      - str
      - No
      - Defaults to ``settings.DEFAULT_FROM_EMAIL``
    * - subject
      - str (context vars allowed)
      - No
      - Subject of Email, if ``template`` is not specified
    * - message
      - str (context vars allowed)
      - No
      - Content of Email, if ``template`` is not specified
    * - html_message
      - str (context vars allowed)
      - No
      - HTML content of Email, if ``template`` is not specified
    * - template
      - str | EmailMerge
      - No
      - EmailMerge instance or name
    * - language
      - str
      - No
      - Language (code) in which you want to send email. Defaults to ``settings.LANGUAGE_CODE``.
    * - cc
      - List[str | EmailAddress]
      - No
      - List of emails in cc(Carbon copy) field
    * - bcc
      - List[str | EmailAddress]
      - No
      - List of emails in bcc(Blind carbon copy) field
    * - attachments
      - dict
      - No
      - Email attachments - a dict where the keys are the filenames and the values are files, file-like-objects or path to file
    * - context
      - dict
      - No
      - Dictionary where keys are strings and values are any serializable objects. Used to render email
    * - headers
      - dict
      - No
      - Extra headers on the message
    * - scheduled_time
      - datetime | date
      - No
      - Indicates when the message should be sent
    * - expires_at
      - datetime | date
      - No
      - If specified, mails that are not yet sent won't be delivered after this date.
    * - expires_at
      - datetime | date
      - No
      - If specified, mails that are not yet sent won't be delivered after this date.
    * - priority
      - str
      - No
      - ``high``, ``medium``, ``low`` or ``now`` (send immediately)
    * - backend
      - str
      - No
      - Alias of the backend you want to use from ``settings.SENDMAIL['BACKENDS']``. Defaults to ``default``

**Note:** Some arguments can take strings with special variables allowed.
Examples of special variables include: ``#var1#``, ``#recipient.first_name#``, etc.

.. code-block:: python

    from sendmail import mail

    mail.send(
        [EmailAddress.objects.create(email='peter@gmail.com', first_name='Peter'), 'lena@email.com', 'ben@yahoo.com'],
        'from@example.com',
        subject='My email',
        message='Hi there!',
        html_message='Hi <strong>#where#</strong>!',
        context={'where': 'there'},
        cc=['cc1@email.com'],
        bcc=['bcc1@email.com', 'bcc2@email.com']
    )

The command above will queue 1 email specified lists of recipients. HTML message will be equal to Hi **there**!

Passing ``now`` as the priority allows to bypass the queue and deliver the email right away.

.. code-block:: python

   from sendmail import mail

    mail.send(
        'recipient@example.com', # List of email addresses or list of EmailAddress also accepted
        'from@example.com',
        template='your-template-here', # Could be an EmailTemplate instance or name
        context={'generator': 'sendmail',
        'username': 'michaelpoi',}, # Context is used to fill both {{ var }} in html and #var# in ckeditor.
        language='en', # If not specified settings.LANGUAGE_CODE is used,
        priority='now'
    )


EmailAddress and recipient context
---------------------------------------

In the sendmail recipients are stored as EmailAddress model instances. This was done to allow personalization of emails.
EmailAddress model has the following attributes:

.. list-table:: EmailAddress attributes
    :widths: 25 20 20 25 35 100
    :header-rows: 1

    * - Attribute
      - Type
      - Req.
      - Signature text
      - Signature html
      - Description
    * - email
      - str
      - Yes
      - #recipient.email#
      - {{ recipient.email }}
      - Recipient email address, can also be a display name (Johh <johh@email.com>)
    * - first_name
      - str
      - No
      - #recipient.first_name#
      - {{ recipient.first_name }}
      - Recipient first name.
    * - last_name
      - str
      - No
      - #recipient.last_name#
      - {{ recipient.last_name }}
      - Recipient surname.
    * - gender
      - str
      - No
      - #recipient.gender#
      - {{ recipient.gender }}
      - Recipient gender. Can be ``male``, ``female`` or ``other``. Is useful to generate greetings in HTML templates.
    * - preferred_language
      - str
      - No
      - \-
      - {{ recipient.preferred_language }}
      - Recipient preferred_language. If using :ref:`mail.send_many()` without language argument email to a certain user will be translated.
        If specified here language is not in ``settings.LANGUAGES`` default will be used.
    * - is_blocked
      - bool
      - No
      - \-
      - \-
      - Defaults to False. If set to True recipient wont get any emails, no matter with :ref:`mail.send()` or :ref:`mail.send_many()`

Every time you use :ref:`mail.send()` or :ref:`mail.send_many()` list of recipients and cc or bcc (only for :ref:`mail.send()` ) are transformed to a list
of EmailAddress instances. If recipient is in database it just selects it by email, otherwise creates a new instance with ``None`` for
all non-required fields.

Recipient context is always passed to extend email context, however:

- If you use :ref:`mail.send()` only 1 email is generated, so the context for the first recipient in a list is used to render email.
- If you use :ref:`mail.send_many()` recipient context is passed to all emails generated.

Recipient context can be used in all phases of template creation (see more :ref:`Templating`).
For example you can add to html template something like this:

.. code-block:: django

    {% with gender=recipient.gender %}
            {% if gender == 'male' %}
                Mr.
                {% elif gender == 'female' %}
                Ms.
                {% else %}
                Human
            {% endif %}
        {% endwith %}
    {{ recipient.first_name }} {{ recipient.last_name }}

This way you can achieve personalized greeting for each recipient when using :ref:`mail.send_many()`.

You can use this context when filling subject, content or placeholders values in CKEditor fields as well. For example:

.. code-block:: python

    from sendmail import mail
    from sendmail.models import EmailAddress

    john = EmailAddress.objects.create(email='john.doe@email.com',
                                       first_name='John',
                                       last_name='Doe')

    mail.send(
        'john.doe@email.com',
        'from@example.com',
        subject='Message for #recipient.first_name#',
        html_message = '<h1>#recipient.first_name# #recipient.last_name#</h1>'
    )

mail.send_many()
-----------------

``mail.send_many()`` is one of the most important function in the library. It is used to generate n (number of recipients)
emails (one for each recipient in ``recipients``).
``mail.send_many()`` is much more efficient alternative for :ref:`mail.send()` , because it utilizes much less database queries.
Using ``mail.send_many()`` you can maximize personalization like discussed in section above.
``mail.send_many()`` takes the same set of parameters like :ref:`mail.send()` , except:

- ``cc`` and ``bcc`` can not be used in ``mail.send_many()``
- ``priority`` can not be ``now``

Other parameters are shared among generated emails.

.. code-block:: python

    import tempfile
    from sendmail import mail
    from sendmail.models import EmailAddress

    lena = EmailAddress.objects.create(email='lena@email.com', first_name='Lena')
    ben = EmailAddress.objects.create(email='ben@yahoo.com', first_name='Ben', is_blocked=True)

    with tempfile.NamedTemporaryFile(delete=True) as f:
        f.write(b'Testing attachments')
        f.seek(0)

        mail.send_many(
            recipients=[EmailAddress.objects.create(email='bob@gmail.com', first_name='Bob'), 'lena@email.com', 'ben@yahoo.com'],
            sender='from@email.com',
            subject='Hello #recipient.first_name#',
            message='This is a letter #id#',
            context={'id': 453},
            language='en',
            attachments={'new_test.txt': f},
        )

Running this will result in 2 emails queued (because user ben is_blocked and hence is excluded).
Subjects will be personalized as "Hello Bob" and "Hello Lena". Content will be the same: "This is a letter 453".
Both emails have the same attachment.

Templating
------------

sendmail introduces a two-phase approach for creating email templates. This process ensures a flexible and powerful way to handle email templates, leveraging both HTML expertise and user-friendly editing tools.

1. :ref:`HTML Base File Creation`
    In the first phase, experienced email HTML developers create base files while adhering to the specific limitations of rendering emails in various clients. During this phase, developers can:

    - Embed images using the {% inline_image %}(see more :ref:`Inlines`) template tag.
    - Insert placeholders using the {% placeholder %} template tag, which will be filled in the second phase.

These base files act as a foundation for further customization.

2. :ref:`CKEDITOR Placeholders editor`
    Once the base file is ready, users can move on to the second phase. Using the admin interface, they select the base file and fill in the placeholders defined in the previous phase. In this phase, users can:

    - Create rich content such as lists, tables, headers, and more features allowed by the configuration in ``settings.CKEDITOR_CONFIGS``.
    - Embed images, which will automatically be converted to a suitable format for sending via email.

This two-step process provides both technical flexibility for developers and ease of use for non-technical users.

HTML Base File Creation
^^^^^^^^^^^^^^^^^^^^^^^^^^

Base Files should be stored in ``settings.TEMPLATES['DIRS'] / 'email'``.
sendmail looks for email folders in all specified DIRS.

In each of your base files you should load sendmail to use custom tags, which can be done as following:

``{% load sendmail %}``

In your templates you can specify variables to be filled with the context:

.. code-block:: django

    {% load sendmail %}

    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Example email template</title>
    </head>
    <body>
        Hello, {{ username }}
        {% placeholder 'main' %}
    </body>
    </html>

username variable is expected then to be filled with :ref:`mail.send()` or :ref:`mail.send_many()` context. If it wont be passed user
wont see any errors. You can still handle this using django build-in filters, for example:

``Hello, {{ username|default:'user'}}``

In your templates you may want to use placeholders inside conditions, loops or includes. With sendmail it is possible.

main.html

.. code-block:: django

    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Title</title>
    </head>
    <body>
    {% if True %}
    {% placeholder 'basic1' %}
    {% placeholder 'basic2' %}
        {% else %}
        {% placeholder 'basic3' %}
    {% endif %}
    {% include 'email/in.html' %}

    </body>
    </html>

in.html

.. code-block:: django

    {% load sendmail %}

    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Title</title>
    </head>
    <body>
    {% placeholder 'include1' %}
    {% placeholder 'include2' %}

    </body>
    </html>

All placeholders in the previous example will be parsed successfully and provided for users.

.. warning::
    Placeholders are not recognized in child templates when using the Django {% extends %} tag.

Inlines
^^^^^^^^^^^^^^^

You may want to use embed images to your templates. This can be done using sendmail ``{% inline_image %}`` template tag.

``<img src="{% inline_image 'images/logo.png' %}" alt="" width="100">``

You can specify either alias or absolute path to your image. Alias are resolved in the following order:

1. In MEDIA_ROOT
2. In ``static`` (using ``django.contrib.staticfiles.finder``)

If no file found ``FileNotFoundError`` exception will be raised

CKEDITOR Placeholders editor
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When needed base file was created, users can create 2-phase templates using it. For it you should simply:

1. Open admin interface and click create new EmailMergeModel.
2. Enter a name which will be used as an template alias for sending.
3. Click "Save and continue editing" (This event is also triggered when a base file is changing)
4. Forms for placeholders editing will appear with defaults, such as:

    Placeholder: <name>, Language: <lang_code>

5. Fill these placeholders with your rich content (you can include variables like #var#, #price#, etc. or recipients context
(see more :ref:`EmailAddress and recipient context`))

Multilingual Templates
------------------------------

In sendmail you can create and send templates in multiple languages. For this simply edit your ``settings.py``:

Verify that internalization is enabled:

.. code-block:: python

    USE_I18N = True

Default templates language can be changed in ``settings.LANGUAGE_CODE``

.. code-block:: python

    LANGUAGE_CODE = 'en'

List of all translation languages should be specified in ``settings.LANGUAGES``

.. code-block:: python

    LANGUAGES = [
    ('en', 'English'),
    ('de', 'German'),
    ]

Adjust this as needed.

The default language will be used when:

1. Language for :ref:`mail.send()` is not provided or is not valid (not in ``LANGUAGES``)
2. if :ref:`mail.send_many()` language is not set and recipient preferred language is ``None`` or not valid

If :ref:`mail.send_many()` is called with defined language then all the emails will be forced to that language.
Otherwise each email is translated to recipient ``preferred language`` if it is available.
Extra attachments are also translated to this language.

.. code-block:: python

    from sendmail.mail import send_many
    from sendmail.models import EmailAddress

    en_recipient = EmailAddress.objects.create(email='en@gmail.com', first_name='John', preferred_language='en')
    de_recipient = EmailAddress.objects.create(email='de@gmail.com', first_name='Ali', preferred_language='de')

    send_many(recipients=[en_recipient, de_recipient], template='your-template', language='en')

In this case de_recipient also gets English copy of an email. To use preferred language you can do something like this:

.. code-block:: python

    from sendmail.mail import send_many
    from sendmail.models import EmailAddress

    en_recipient = EmailAddress.objects.create(email='en@gmail.com', first_name='John', preferred_language='en')
    de_recipient = EmailAddress.objects.create(email='de@gmail.com', first_name='Ali', preferred_language='de')

    send_many(recipients=[en_recipient, de_recipient], template='your-template')

Now de_recipient gets German letter and en_recipient English copy.

Custom Email Backends
---------------------------

By default sendmail uses ``django.core.mail.backends.smtp.EmailBackend``.
If you want to use other email backends, you can change it by configuring ``settings.SENDMAIL['BACKENDS']``

For example to use `django-ses <https://github.com/django-ses/django-ses>`_ you can do:

.. code-block:: python

    SENDMAIL = {
    # other settings
    'BACKENDS': {
        'default': 'django.core.mail.backends.smtp.EmailBackend',
        'ses': 'django_ses.SESBackend',
        }
    }

Now when you use :ref:`mail.send()` or :ref:`mail.send_many()` you can which backend will be used for sending by specifying
``backend`` argument. If ``backend`` is not specified ``default`` will be used.

**Note** For :ref:`mail.send_many()` all generated emails will inherit ``backend`` argument.

.. code-block:: python

    from sendmail import mail

    mail.send(
    ['recipient@example.com'],
    'from@example.com',
    subject='Hello',
    )

Resulting email will be sent using ``default`` backend.

.. code-block:: python

    from sendmail import mail

    mail.send_many(
    recipients=['recipient@example.com', 'next@gmail.com'],
    sender='from@example.com',
    subject='Hello',
    backend='ses'
    )

Resulting 2 emails will be sent using ``django-ses`` backend.

Management commands
------------------------

- send_queued_mail - send queued emails, those are not successfully sent are marked as failed or requeued depending on :ref:`settings`.

.. list-table:: send_queued_mail arguments
   :widths: 50 100
   :header-rows: 1

   * - Argument
     - Description
   * - --processes or -p
     - Number of concurrent processes to send queued emails. Defaults to ``1``.
   * - --log-level or -l
     - Log level ``0`` to log nothing, ``1`` to log only errors. Defaults to ``2`` - log everything.


- cleanup_mail - delete all emails created before an X number of days (defaults to 90).

.. list-table:: cleanup_mail arguments
   :widths: 50 100
   :header-rows: 1

   * - Argument
     - Description
   * - --days or -d
     - Email older than this argument will be deleted. Defaults to ``90``.
   * - --delete-attachments or -da
     - Flag to delete orphaned attachment records and files on disk. If not specified attachments wont be deleted.
   * - --batch-size or -b
     - Limits number of emails being deleted in a batch. Defaults to ``1000``.

- dblocks - when ``sendmail`` is sending emails using ``send_queued_mail`` management command it blocks the entire database.
  You can use this command to manage these DB locks.

.. list-table:: dblocks
   :widths: 50 100
   :header-rows: 1

   * - Argument
     - Description
   * - --delete or -d
     - Delete expired locks.
   * - --delete-all
     - Delete all locks.




















