import secrets
import string

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from industries.models import Industry

User = get_user_model()


class Company(models.Model):
    company_name = models.CharField(max_length=255)
    industry = models.ForeignKey(Industry, on_delete=models.CASCADE, related_name='companies')
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='company_profile')
    username = models.CharField(max_length=255, unique=True, blank=True)
    # This stores generated plain credentials for company onboarding view.
    password = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Companies'

    def __str__(self):
        return self.company_name

    def _generate_username(self):
        base = slugify(self.company_name).replace('-', '_') or 'company'
        # Include current second in username and keep retrying with a short suffix
        # to guarantee uniqueness even when many rows are created in the same second.
        second_part = timezone.now().strftime('%Y%m%d%H%M%S')
        counter = 0
        while True:
            extra = '' if counter == 0 else f'_{counter}'
            candidate = f'{base}_{second_part}{extra}'
            if not Company.objects.filter(username=candidate).exists() and not User.objects.filter(username=candidate).exists():
                return candidate
            counter += 1

    def _generate_password(self):
        alphabet = string.ascii_letters + string.digits
        random_part = ''.join(secrets.choice(alphabet) for _ in range(8))
        second_part = timezone.now().strftime('%H%M%S')
        return f'{random_part}{second_part}'

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if not self.username:
            self.username = self._generate_username()
        if not self.password:
            self.password = self._generate_password()
        super().save(*args, **kwargs)
        if is_new and not self.user:
            self.user = User.objects.create_user(
                username=self.username,
                password=self.password,
            )
            super().save(update_fields=['user'])

    def delete(self, *args, **kwargs):
        linked_user = self.user
        super().delete(*args, **kwargs)
        if linked_user:
            linked_user.delete()
