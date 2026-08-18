"""Grant staff rights, so an account can check tickets in at the door."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

User = get_user_model()


class Command(BaseCommand):
    help = "Give an account staff rights (needed for ticket check-in)."

    def add_arguments(self, parser):
        parser.add_argument("email")
        parser.add_argument(
            "--revoke", action="store_true", help="Take the rights away instead."
        )

    def handle(self, *args, **options):
        try:
            user = User.objects.get(email=options["email"].lower())
        except User.DoesNotExist as exc:
            raise CommandError(f"No account for {options['email']}.") from exc

        user.is_staff = not options["revoke"]
        user.save(update_fields=["is_staff"])

        state = "revoked from" if options["revoke"] else "granted to"
        self.stdout.write(self.style.SUCCESS(f"Staff rights {state} {user.email}."))
