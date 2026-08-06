import logging
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import SystemNotification
from companies.models import (
    MandatoryGuideline,
    SectionInternalGuideline,
)
from professions.models import Profession
from accounts.models import UserProfile
from django.contrib.auth.models import User
from django.db.models import Q

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Checks for expired guidelines and sends SystemNotifications to relevant users."

    def add_arguments(self, parser):
        parser.add_argument(
            '--days-ahead',
            type=int,
            nargs='+',
            default=[0, 1, 3],
            help='List of days ahead to notify (e.g., 0 for today, 1 for tomorrow).'
        )

    def handle(self, *args, **options):
        days_ahead_list = options['days_ahead']
        now = timezone.now()
        
        self.stdout.write(f"Starting check for expired guidelines at {now}")

        for days_ahead in days_ahead_list:
            target_date = (now + timedelta(days=days_ahead)).date()
            self.stdout.write(f"Checking for guidelines expiring on {target_date} ({days_ahead} days left)")

            self.check_mandatory_guidelines(target_date, days_ahead)
            self.check_internal_guidelines(target_date, days_ahead)
            self.check_profession_guidelines(target_date, days_ahead)

        self.stdout.write(self.style.SUCCESS("Successfully completed expired guidelines check."))

    def create_notification(self, users, title, message, url_path):
        notifications = []
        for user in users:
            notifications.append(
                SystemNotification(
                    user=user,
                    title=title,
                    message=message,
                    type='guideline',
                    url=url_path,
                )
            )
        if notifications:
            SystemNotification.objects.bulk_create(notifications)
            self.stdout.write(f"Created {len(notifications)} notifications for '{title}'")

    def _get_department_users(self, department):
        # Includes department admins, section admins, and workers
        return User.objects.filter(
            Q(profile__department=department) | Q(section_memberships__section__department=department)
        ).distinct()
        
    def _get_section_users(self, section):
        # Includes section admins and workers in that section
        return User.objects.filter(
            Q(profile__section=section) | Q(section_memberships__section=section)
        ).distinct()

    def check_mandatory_guidelines(self, target_date, days_ahead):
        guidelines = MandatoryGuideline.objects.filter(
            active_until__date=target_date
        )
        for g in guidelines:
            title = self._get_title("Majburiy yo'riqnoma", days_ahead)
            message = f"'{g.name}' yo'riqnomasining {self._get_message_suffix(days_ahead)}."
            users = self._get_department_users(g.department)
            self.create_notification(users, title, message, '/majburiy-yoriqnomalar/')

    def check_internal_guidelines(self, target_date, days_ahead):
        guidelines = SectionInternalGuideline.objects.filter(
            active_until__date=target_date
        )
        for g in guidelines:
            title = self._get_title("Ichki yo'riqnoma", days_ahead)
            message = f"'{g.name}' yo'riqnomasining {self._get_message_suffix(days_ahead)}."
            users = self._get_section_users(g.section)
            self.create_notification(users, title, message, '/ichki-yoriqnomalar/')

    def check_profession_guidelines(self, target_date, days_ahead):
        guidelines = Profession.objects.filter(
            active_until__date=target_date
        )
        for g in guidelines:
            title = self._get_title("Kasb yo'riqnomasi", days_ahead)
            message = f"'{g.name}' yo'riqnomasining {self._get_message_suffix(days_ahead)}."
            # Profession is organization level, notify all users with this profession
            users = User.objects.filter(
                profile__profession_memberships__profession=g
            ).distinct()
            self.create_notification(users, title, message, '/kasb-yoriqnomasi/')

    def _get_title(self, base_type, days_ahead):
        if days_ahead == 0:
            return f"{base_type} muddati bugun tugaydi"
        elif days_ahead < 0:
            return f"{base_type} muddati o'tgan"
        else:
            return f"{base_type} muddati tugashiga {days_ahead} kun qoldi"

    def _get_message_suffix(self, days_ahead):
        if days_ahead == 0:
            return "muddati bugun o'z nihoyasiga yetadi"
        elif days_ahead < 0:
            return "muddati o'tib ketdi va bloklandi"
        else:
            return f"tugashiga {days_ahead} kun qoldi"
