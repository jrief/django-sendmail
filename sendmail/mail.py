from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection as db_connection
from django.db.models import Q
from django.utils import timezone
from email.utils import make_msgid

from .connections import connections
from .logutils import setup_loghandlers
from .models import EmailModel, EmailMergeModel, Log, PRIORITY, STATUS, Recipient, EmailAddress
from .settings import (
    get_available_backends,
    get_batch_size,
    get_log_level,
    get_max_retries,
    get_message_id_enabled,
    get_message_id_fqdn,
    get_retry_timedelta,
    get_sending_order, get_default_language
)
from .signals import email_queued
from .utils import (
    create_attachments,
    get_email_template,
    parse_emails,
    parse_priority,
    get_recipients_objects, set_recipients,
    get_or_create_recipient, get_language_from_code,
)
from django.db import transaction

logger = setup_loghandlers('INFO')


def create(
        sender,
        recipients=None,
        cc=None,
        bcc=None,
        subject='',
        message='',
        html_message='',
        context=None,
        scheduled_time=None,
        expires_at=None,
        headers=None,
        template=None,
        priority=None,
        commit=True,
        backend='',
        language='',
):
    """
    Creates an email from supplied keyword arguments. If template is
    specified, email subject and content will be rendered during delivery.
    """

    if not language:
        language = get_default_language()
    priority = parse_priority(priority)
    status = None if priority == PRIORITY.now else STATUS.queued

    if recipients is None:
        recipients = []
    if cc is None:
        cc = []
    if bcc is None:
        bcc = []
    if context is None:
        context = {}
    message_id = make_msgid(domain=get_message_id_fqdn()) if get_message_id_enabled() else None
    recipients_addresses = get_recipients_objects(recipients)
    cc_addresses = get_recipients_objects(cc)
    bcc_addresses = get_recipients_objects(bcc)

    if commit and template:
        bcc_addresses.extend(list(template.extra_recipients.all()))

    if not (recipient := context.get('recipient', None)):  # If recipient is not set use the first one from the list
        context['recipient'] = get_or_create_recipient(recipients[0]).id
    else:
        if isinstance(recipient, EmailAddress):
            context['recipient'] = recipient.id

    if template:
        translated_content = template.translated_contents.get(language=language)
        subject = translated_content.subject
        message = translated_content.content

    email = EmailModel(
        subject=subject,
        message=message,
        html_message=html_message,
        from_email=sender,
        scheduled_time=scheduled_time,
        expires_at=expires_at,
        message_id=message_id,
        headers=headers,
        priority=priority,
        status=status,
        context=context,
        template=template,
        backend_alias=backend,
        language=language
    )

    if commit:
        with transaction.atomic():
            email.save()
            set_recipients(email, recipients_addresses, cc_addresses, bcc_addresses)

    return email


def send(
        recipients=None,
        sender=None,
        template=None,
        context=None,
        subject='',
        message='',
        html_message='',
        scheduled_time=None,
        expires_at=None,
        headers=None,
        priority=None,
        attachments=None,
        log_level=None,
        commit=True,
        cc=None,
        bcc=None,
        language='',
        backend='',
):
    language = get_language_from_code(language)
    try:
        recipients = parse_emails(recipients)
    except ValidationError as e:
        raise ValidationError('recipients: %s' % e.message)

    try:
        cc = parse_emails(cc)
    except ValidationError as e:
        raise ValidationError('c: %s' % e.message)

    try:
        bcc = parse_emails(bcc)
    except ValidationError as e:
        raise ValidationError('bcc: %s' % e.message)

    if sender is None:
        sender = settings.DEFAULT_FROM_EMAIL

    priority = parse_priority(priority)

    if log_level is None:
        log_level = get_log_level()

    if not commit:
        if priority == PRIORITY.now:
            raise ValueError("send_many() can't be used with priority = 'now'")

    if template:
        if subject:
            raise ValueError('You can\'t specify both "template" and "subject" arguments')
        if message:
            raise ValueError('You can\'t specify both "template" and "message" arguments')
        if html_message:
            raise ValueError('You can\'t specify both "template" and "html_message" arguments')

        # template can be an EmailMerge instance or name
        if not isinstance(template, EmailMergeModel):
            template = get_email_template(template)

    if backend and backend not in get_available_backends().keys():
        raise ValueError('%s is not a valid backend alias' % backend)

    email = create(
        sender,
        recipients,
        cc,
        bcc,
        subject,
        message,
        html_message,
        context,
        scheduled_time,
        expires_at,
        headers,
        template,
        priority,
        commit=commit,
        backend=backend,
        language=language
    )

    if attachments and commit:
        attachments = create_attachments(attachments)
        email.attachments.add(*attachments)

    if template and commit:
        extra_attachments = template.translated_contents.get(language=language).extra_attachments.all()
        email.attachments.add(*extra_attachments)

    if priority == PRIORITY.now:
        email.dispatch(log_level=log_level)
    elif commit:
        email_queued.send(sender=EmailModel, emails=[email])

    return email


def send_many(**kwargs):
    """
    This function allows to send multiple emails separately. Using it is beneficial if you need a user data as a
    context and you want to serve every recipient separately.
    """
    if not (recipients := parse_emails(kwargs.pop('recipients', None))):
        raise ValueError('You must specify recipients')
    if kwargs.get('cc') or kwargs.get('bcc'):
        raise ValueError('send_many() can not be used with cc, bcc')

    recipients_objs = get_recipients_objects(recipients)

    context = kwargs.pop('context', {})
    if kwargs.get('language'):
        emails = [
            send(recipients=[recipient.email],
                 context={**context, 'recipient': recipient.id},
                 commit=False,
                 **kwargs)
            for recipient in recipients_objs]
    else:
        emails = [
            send(recipients=[recipient.email],
                 context={**context, 'recipient': recipient.id},
                 commit=False,
                 language=recipient.preferred_language,
                 **kwargs)
            for recipient in recipients_objs]

    if emails:
        emails = EmailModel.objects.bulk_create(emails)

        email_recipients = []
        for email, recipient in zip(emails, recipients_objs):
            email_recipients.append(Recipient(email=email, address=recipient, send_type='to'))
        Recipient.objects.bulk_create(email_recipients)

        if attachments := kwargs.get('attachments', None):
            through_objs = []
            attach_objs = create_attachments(attachments)

            if template := kwargs.get('template'):
                if not isinstance(template, EmailMergeModel):
                    template = get_email_template(template)

            extra_attachments_cache = {}

            for email, emailaddress in zip(emails, recipients_objs):
                language = get_language_from_code(emailaddress.preferred_language, log=False)

                if language not in extra_attachments_cache:
                    extra_attachments = template.translated_contents.get(language=language).extra_attachments.all()
                    extra_attachments_cache[language] = extra_attachments
                else:
                    extra_attachments = extra_attachments_cache[language]

                for attach in [*attach_objs, *extra_attachments]:
                    through_objs.append(email.attachments.through(emailmodel_id=email.id, attachment_id=attach.id))

            emails[0].attachments.through.objects.bulk_create(through_objs)

        for batch in split_into_batches(emails):
            email_queued.send(sender=EmailModel, emails=batch)

        return emails


def split_into_batches(emails):
    n = get_batch_size()
    return [emails[i:i + n] for i in range(0, len(emails), n)]


def get_queued():
    """
    Returns the queryset of emails eligible for sending – fulfilling these conditions:
     - Status is queued or requeued
     - Has scheduled_time before the current time or is None
     - Has expires_at after the current time or is None
    """
    now = timezone.now()
    query = (Q(scheduled_time__lte=now) | Q(scheduled_time=None)) & (Q(expires_at__gt=now) | Q(expires_at=None))
    return (
        EmailModel.objects.filter(query, status__in=[STATUS.queued, STATUS.requeued])
        .select_related('template')
        .order_by(*get_sending_order())
        .prefetch_related('attachments')[: get_batch_size()]
    )


def _send_bulk(emails, uses_multiprocessing=True, log_level=None):
    # Multiprocessing does not play well with database connection
    # Fix: Close connections on forking process
    # https://groups.google.com/forum/#!topic/django-users/eCAIY9DAfG0
    if uses_multiprocessing:
        db_connection.close()

    if log_level is None:
        log_level = get_log_level()

    sent_emails = []
    failed_emails = []  # This is a list of two tuples (email, exception)
    email_count = len(emails)

    logger.info('Process started, sending %s emails' % email_count)

    def send(email):
        try:
            email.dispatch(log_level=log_level, commit=False, disconnect_after_delivery=False)
            sent_emails.append(email)
            logger.debug('Successfully sent email #%d' % email.id)
        except Exception as e:
            logger.exception('Failed to send email #%d' % email.id)
            failed_emails.append((email, e))

    # Prepare emails before we send these to threads for sending
    # So we don't need to access the DB from within threads
    for email in emails:
        # Sometimes this can fail, for example when trying to render
        # email from a faulty Django template
        try:
            email.prepare_email_message()
        except Exception as e:
            logger.exception('Failed to prepare email #%d' % email.id)
            failed_emails.append((email, e))

    for email in emails:
        send(email)

    connections.close()

    # Update statuses of sent emails
    email_ids = [email.id for email in sent_emails]
    EmailModel.objects.filter(id__in=email_ids).update(status=STATUS.sent)

    # Update statuses and conditionally requeue failed emails
    num_failed, num_requeued = 0, 0
    max_retries = get_max_retries()
    scheduled_time = timezone.now() + get_retry_timedelta()
    emails_failed = [email for email, _ in failed_emails]

    for email in emails_failed:
        if email.number_of_retries is None:
            email.number_of_retries = 0
        if email.number_of_retries < max_retries:
            email.number_of_retries += 1
            email.status = STATUS.requeued
            email.scheduled_time = scheduled_time
            num_requeued += 1
        else:
            email.status = STATUS.failed
            num_failed += 1

    EmailModel.objects.bulk_update(emails_failed, ['status', 'scheduled_time', 'number_of_retries'])

    # If log level is 0, log nothing, 1 logs only sending failures
    # and 2 means log both successes and failures
    if log_level >= 1:
        logs = []
        for email, exception in failed_emails:
            logs.append(
                Log(
                    email=email,
                    status=STATUS.failed,
                    message=str(exception),
                    exception_type=type(exception).__name__,
                )
            )

        if logs:
            Log.objects.bulk_create(logs)

    if log_level == 2:
        logs = []
        for email in sent_emails:
            logs.append(Log(email=email, status=STATUS.sent))

        if logs:
            Log.objects.bulk_create(logs)

    logger.info(
        'Process finished, %s attempted, %s sent, %s failed, %s requeued',
        email_count,
        len(sent_emails),
        num_failed,
        num_requeued,
    )

    return len(sent_emails), num_failed, num_requeued
