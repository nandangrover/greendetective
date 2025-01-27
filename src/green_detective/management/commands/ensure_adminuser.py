import os
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from detective.models import Business, UserProfile


class Command(BaseCommand):
    help = "Creates an admin user non-interactively if it doesn't exist"

    def add_arguments(self, parser):
        parser.add_argument("--username", help="Admin's username")
        parser.add_argument("--email", help="Admin's email")
        parser.add_argument("--password", help="Admin's password")
        parser.add_argument(
            "--noinput", help="Read options from the environment", action="store_true"
        )

    def handle(self, *args, **options):
        User = get_user_model()

        if options["noinput"]:
            options["username"] = os.environ["DJANGO_SUPERUSER_USERNAME"]
            options["email"] = os.environ["DJANGO_SUPERUSER_EMAIL"]
            options["password"] = os.environ["DJANGO_SUPERUSER_PASSWORD"]

        if not User.objects.filter(username=options["username"]).exists():
            # Create admin user
            user = User.objects.create_superuser(
                username=options["username"],
                email=options["email"],
                password=options["password"],
            )

            # Create default business
            business = Business.objects.create(
                name="Admin Business",
                website="https://admin.example.com",
                industry="Technology",
                size="1-10",
            )

            # Update user profile
            profile = UserProfile.objects.get(user=user)
            profile.business = business
            profile.job_title = "Administrator"
            profile.save()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully created admin user {options['username']} with default business"
                )
            )
