# accounts/management/commands/hash_passwords.py

from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password
from accounts.models import CustomUser


class Command(BaseCommand):
    help = "Hashes plain text passwords for all users in accounts_customers table"

    def handle(self, *args, **kwargs):
        # Fetch all users from the database
        users = CustomUser.objects.all()
        updated_count = 0

        for user in users:
            if not user.password.startswith(
                "pbkdf2_sha256$"
            ):  # Check if the password is already hashed
                user.password = make_password(user.password)
                user.save()
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully hashed passwords for {updated_count} users"
            )
        )
