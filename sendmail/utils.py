from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.contrib.staticfiles.finders import find
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import F
from django.utils.encoding import force_str

from sendmail import cache
from sendmail.logutils import setup_loghandlers
from sendmail.models.attachment import Attachment
from sendmail.models.emailaddress import Recipient
from sendmail.models.emailmerge import EmailMergeModel
from sendmail.models.emailmodel import PRIORITY, STATUS, EmailModel
from sendmail.settings import get_default_language, get_default_priority, get_email_address_model, get_languages_list
from sendmail.signals import email_queued
from sendmail.validators import validate_email_with_name

logger = setup_loghandlers('INFO')


def send_mail(
        subject,
        message,
        from_email,
        recipient_list,
        html_message='',
        scheduled_time=None,
        headers=None,
        priority=PRIORITY.medium,
        language=''
):
    """
    Add a new message to the mail queue. This is a replacement for Django's
    ``send_mail`` core email method.
    """

    if not language:
        language = get_default_language()

    subject = force_str(subject)
    status = None if priority == PRIORITY.now else STATUS.queued
    emails = []
    for address in recipient_list:
        email = EmailModel.objects.create(
            from_email=from_email,
            subject=subject,
            message=message,
            html_message=html_message,
            status=status,
            headers=headers,
            priority=priority,
            scheduled_time=scheduled_time,
            language=language,
        )
        set_recipients(email, [get_or_create_recipient(address)])

        emails.append(email)

    if priority == PRIORITY.now:
        for email in emails:
            email.dispatch()
    else:
        email_queued.send(sender=EmailModel, emails=emails)
    return emails


def get_emailmerge(name):
    """
    Function that returns an EmailMerge instance, from cache or DB.
    """
    use_cache = getattr(settings, 'SENDMAIL_CACHE', True)
    if use_cache:
        use_cache = getattr(settings, 'SENDMAIL_TEMPLATE_CACHE', True)
    if not use_cache:
        return EmailMergeModel.objects.get(name=name)
    else:
        composite_name = '%s' % name
        email_template = cache.get(composite_name)

        if email_template is None:
            email_template = EmailMergeModel.objects.get(name=name)
            cache.set(composite_name, email_template)

        return email_template


def split_emails(emails, split_count=1):
    # Group emails into X sublists
    # taken from http://www.garyrobinson.net/2008/04/splitting-a-pyt.html
    # Strange bug, only return 100 email if we do not evaluate the list
    if list(emails):
        return [emails[i::split_count] for i in range(split_count)]

    return []


def create_attachments(attachment_files):
    """
    Create Attachment instances from files

    attachment_files is a dict of:
        * Key - the filename to be used for the attachment.
        * Value - file-like object, or a filename to open OR a dict of {'file': file-like-object, 'mimetype': string}

    Returns a list of Attachment objects
    """
    attachments = []
    for filename, filedata in attachment_files.items():
        if isinstance(filedata, dict):
            content = filedata.get('file', None)
            mimetype = filedata.get('mimetype', None)
            headers = filedata.get('headers', None)
        else:
            content = filedata
            mimetype = None
            headers = None

        opened_file = None

        if isinstance(content, str):
            # `content` is a filename - try to open the file
            if default_storage.exists(content):
                opened_file = default_storage.open(content, 'rb')
            else:
                raise FileNotFoundError(f'File {content} not found in storage.')

            content = File(opened_file)

        attachment = Attachment()
        if mimetype:
            attachment.mimetype = mimetype
        attachment.headers = headers
        attachment.name = filename
        attachment.file.save(filename, content=content, save=True)

        attachments.append(attachment)

        if opened_file is not None:
            opened_file.close()

    return attachments


def parse_priority(priority):
    """
    Parses and validates the given priority, returning its enum representation
    or a default value if none is provided. This function handles string
    representations of priorities and maps them to corresponding enum values.

    Parameters:
        priority (Optional[Union[str, Enum]]): The priority value to parse, which can be a string or an enum or None.

    Returns:
        Enum: The corresponding enum representation of the priority or a default
        enum value if input is None.

    Raises:
        ValueError: If the priority given as a string does not match any valid
        enum value.
    """
    if priority is None:
        priority = get_default_priority()
    # If priority is given as a string, returns the enum representation
    if isinstance(priority, str):
        priority = getattr(PRIORITY, priority, None)

        if priority is None:
            raise ValueError('Invalid priority, must be one of: %s' % ', '.join(PRIORITY._fields))
    return priority


def parse_emails(emails):
    """
    A function that returns a list of valid email addresses.
    This function will also convert a single email address into
    a list of email addresses.
    None value is also converted into an empty list.
    """

    if isinstance(emails, str):
        emails = [emails]
    elif emails is None:
        emails = []

    for email in emails:
        try:
            validate_email_with_name(email)
        except ValidationError:
            raise ValidationError('%s is not a valid email address' % email)

    return emails


def get_or_create_recipient(email: str):
    obj, _ = get_email_address_model().objects.get_or_create(email=email)
    return obj


def get_recipients_objects(emails):
    """
    Processes a list of emails or EmailAddress instances, deduplicating and
    filtering them, and returns a list of EmailAddress objects that are not
    blocked. The function identifies existing email addresses in the database
    and distinguishes between those that need to be created and those that
    already exist. Blocked emails are logged and excluded from the results.

    Args:
        emails (list[Union[str, EmailAddress]]): A list of email strings or
            EmailAddress instances.

    Returns:
        list[EmailAddress]: A list of EmailAddress objects representing
            non-blocked emails, including newly created ones if they did not
            exist in the database.
    """
    EmailAddress = get_email_address_model()
    unique_emails = []
    seen = set()

    # Separate strings from EmailAddress instances and deduplicate
    for email in emails:
        email_str = email.email if isinstance(email, EmailAddress) else email
        if email_str not in seen:
            unique_emails.append(email)
            seen.add(email_str)

    # Filter only string emails to check existing recipients in the database
    email_strings = [email for email in unique_emails if isinstance(email, str)]
    existing_recipients = EmailAddress.objects.filter(email__in=email_strings)
    existing_emails = {recipient.email: recipient for recipient in existing_recipients}

    recipient_objects = []
    to_create_objects = []

    for email in unique_emails:
        if isinstance(email, EmailAddress):
            if email.pk:
                if not email.is_blocked:
                    recipient_objects.append(email)
                else:
                    logger.warning(f"User {email.email} is blocked and hence will be excluded")
            else:
                to_create_objects.append(email)
        else:
            if email in existing_emails:
                obj = existing_emails[email]
                if obj.is_blocked:
                    logger.warning(f"User {email} is blocked and hence will be excluded")
                else:
                    recipient_objects.append(obj)
            else:
                to_create_objects.append(EmailAddress(email=email))

    # Bulk create new recipients
    if to_create_objects:
        created_objects = EmailAddress.objects.bulk_create(to_create_objects)
        recipient_objects.extend(created_objects)

    return recipient_objects


def set_recipients(email: EmailModel,
                   to_addresses,
                   cc_addresses=None,
                   bcc_addresses=None, ):

    """
    Set recipients for an email by creating 'Recipient' objects for each address and bulk creating
    them in the database. Handles 'to', 'cc', and 'bcc' recipient types.

    Parameters:
        email (EmailModel): The email for which recipients are being set.
        to_addresses (list): List of email addresses to be added as 'to' recipients.
        cc_addresses (list, optional): List of email addresses to be added as 'cc' recipients.
        bcc_addresses (list, optional): List of email addresses to be added as 'bcc' recipients.

    Returns:
        list: A list of created 'Recipient' objects associated with the email.
    """

    to_recipients = [Recipient(email=email,
                               address=addr,
                               send_type='to')
                     for addr in to_addresses]

    if cc_addresses:
        to_recipients.extend([Recipient(email=email,
                                        address=addr,
                                        send_type='cc')
                              for addr in cc_addresses])

    if bcc_addresses:
        to_recipients.extend([Recipient(email=email,
                                        address=addr,
                                        send_type='bcc')
                              for addr in bcc_addresses])

    Recipient.objects.bulk_create(to_recipients)

    return to_recipients


def cleanup_expired_mails(cutoff_date, delete_attachments=True, batch_size=1000):
    """
    Delete all emails before the given cutoff date.
    Optionally also delete pending attachments.
    Return the number of deleted emails and attachments.
    """
    total_deleted_emails = 0

    while True:
        email_ids = EmailModel.objects.filter(created__lt=cutoff_date).values_list('id', flat=True)[:batch_size]
        if not email_ids:
            break

        _, deleted_data = EmailModel.objects.filter(id__in=email_ids).delete()
        if deleted_data:
            total_deleted_emails += deleted_data['sendmail.EmailModel']

    attachments_count = 0
    if delete_attachments:
        while True:
            attachments = Attachment.objects.filter(emails=None)[:batch_size]
            if not attachments:
                break
            attachment_ids = set()
            for attachment in attachments:
                # Delete the actual file
                attachment.file.delete()
                attachment_ids.add(attachment.id)
            deleted_count, _ = Attachment.objects.filter(id__in=attachment_ids).delete()
            attachments_count += deleted_count

    return total_deleted_emails, attachments_count


def get_language_from_code(code, log=True, template=None) -> str:
    if not code:
        return get_default_language()
    else:
        if code not in get_languages_list():
            if log:
                logger.warning(f'Language "{code}" is not found in LANGUAGES configuration or I18N is disabled.')
            return get_default_language()
        if template and code not in template.get_available_languages():
            return get_default_language()

    return code


def update_newsletter_counts(emails, sent_emails, failed_emails):
    Newsletter = apps.get_model('sendmail', 'Newsletter')
    newsletter_set = set([email.newsletter.pk for email in emails if email.newsletter])
    updates = {news: {'sent': 0, 'failed': 0} for news in newsletter_set}
    for email in sent_emails:
        if email.newsletter:
            updates[email.newsletter.pk]['sent'] += 1

    for email, _ in failed_emails:
        if email.newsletter:
            updates[email.newsletter.pk]['failed'] += 1

    newsletters = Newsletter.objects.filter(pk__in=newsletter_set)

    for newsletter in newsletters:
        sent_count = updates[newsletter.pk]['sent']
        failed_count = updates[newsletter.pk]['failed']

        with transaction.atomic():
            newsletter.sent_emails = F('sent_emails') + sent_count
            newsletter.failed_emails = F('failed_emails') + failed_count

            newsletter.save()
            newsletter.check_status()

    return updates

def get_path_from_static(filename):
    """
        Retrieve the full path of a file from the static directory.

        This function searches for a file in a predefined static directory and
        returns its full path as a Path object. If the file is not found, or if
        the file is a directory instead of a file, appropriate exceptions are
        raised.

        Parameters:
        filename: str
            The name of the file to locate in the static directory.

        Returns:
        Path
            The full path object of the requested file.

        Raises:
        FileNotFoundError
            If the file does not exist in the static directory.
        IsADirectoryError
            If the located path is a directory and not a file.
    """
    path = find(filename)
    fullpath = Path(path) if path else None
    if not fullpath:
        raise FileNotFoundError(f"No such file in static: {filename}")
    if not fullpath.is_file():
        raise IsADirectoryError(f"File {filename} is not a file")

    return fullpath

