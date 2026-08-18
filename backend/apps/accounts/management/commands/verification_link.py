"""Print a fresh verification link for an account.

Development convenience: in production the link only ever reaches the user by
email, but while testing locally digging it out of the server log is tedious.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.tokens import make_verification_token, verification_url

User = get_user_model()


class Command(BaseCommand):
    help = "Print a verification link for the given email address."

    def add_arguments(self, parser):
        parser.add_argument("email")
        parser.add_argument(
            "--verify",
            action="store_true",
            help="Skip the link and mark the address confirmed straight away.",
        )

    def handle(self, *args, **options):
        try:
            user = User.objects.get(email=options["email"].lower())
        except User.DoesNotExist as exc:
            raise CommandError(f"No account for {options['email']}.") from exc

        if options["verify"]:
            user.mark_email_verified()
            self.stdout.write(self.style.SUCCESS(f"{user.email} is now verified."))
            return

        if user.is_email_verified:
            self.stdout.write(self.style.WARNING(f"{user.email} is already verified."))
            return

        self.stdout.write(verification_url(make_verification_token(user)))
