from django.core.management.base import BaseCommand
from django.utils.timezone import localtime, now

from sendmail.models.dbmutex import DBMutex
from sendmail.management.commands.subcommands.base import SubcommandsCommand


class Command(SubcommandsCommand):
    help_string = "Manage DB locks."
    command_name = "dblocks"

    def add_arguments(self, parser):
        parser.add_argument('-d', '--delete', dest='delete_expired', action='store_true',
                            help="Delete expired locks.")

        parser.add_argument('--delete-all', action='store_true',
                            help="Delete all locks.")

    def handle(self, verbosity, delete_expired, delete_all, **options):
        num_locks = 0
        if delete_all:
            num_locks, _ = DBMutex.objects.all().delete()
        elif delete_expired:
            num_locks, _ = DBMutex.objects.filter(expires_at__lt=now()).delete()
        if num_locks > 0:
            self.stdout.write("Deleted {} lock(s).".format(num_locks))
        msg = "Lock: '{lock_id}'{expire}."
        for entry in DBMutex.objects.all():
            if entry.expires_at < now():
                expire = " (expired)"
            else:
                expire = " (expires at {})".format(localtime(entry.expires_at.replace(microsecond=0)))
            self.stdout.write(msg.format(lock_id=entry.lock_id, expire=expire))
