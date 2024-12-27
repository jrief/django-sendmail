from collections import OrderedDict
import sendmail
from sendmail.management.commands.subcommands.base import SubcommandsCommand
from sendmail.management.commands.subcommands.cleanup_mail import Command as CleanupMailCommand
from sendmail.management.commands.subcommands.send_queued_mail import SendBatch, SendQueuedMail
from sendmail.management.commands.subcommands.dblocks import Command as DBLocksCommand

class Command(SubcommandsCommand):
    command_name = "sendmail"
    subcommands = OrderedDict((
        ('cleanup_mail', CleanupMailCommand),
        ('all', SendQueuedMail),
        ('batch', SendBatch),
        ('dblocks', DBLocksCommand),
    ))
    missing_args_message = 'one of the available sub commands must be provided'

    subcommand_dest = 'cmd'

    def get_version(self):
        return '.'.join(map(str,sendmail.VERSION))

    def add_arguments(self, parser):
        parser.add_argument('--version', action='version', version=self.get_version())
        super().add_arguments(parser)
