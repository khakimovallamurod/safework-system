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


class Department(models.Model):
    leader = models.ForeignKey(
        'accounts.UserProfile',
        on_delete=models.CASCADE,
        related_name='departments',
    )
    name = models.CharField(max_length=255)
    supervisor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supervised_departments',
        verbose_name='Boshqarma nazoratchisi',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Departments'
        unique_together = ('leader', 'name')

    def __str__(self):
        return self.name


class Section(models.Model):
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='sections',
    )
    name = models.CharField(max_length=255)
    supervisor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supervised_sections',
        verbose_name='Bo‘lim nazoratchisi',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Sections'
        unique_together = ('department', 'name')

    def __str__(self):
        return self.name


class SectionMembership(models.Model):
    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name='memberships',
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='section_memberships',
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-assigned_at']
        verbose_name_plural = 'Section memberships'
        constraints = [
            models.UniqueConstraint(fields=['user'], name='unique_section_member_per_user'),
        ]

    def __str__(self):
        return f'{self.user_id} → {self.section.name}'


class SectionMessage(models.Model):
    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_section_messages',
    )
    title = models.CharField(max_length=255)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Section messages'

    def __str__(self):
        return self.title


class SectionMessageReceipt(models.Model):
    message = models.ForeignKey(
        SectionMessage,
        on_delete=models.CASCADE,
        related_name='receipts',
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='section_message_receipts',
    )
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('message', 'user')
        verbose_name_plural = 'Section message receipts'

    def __str__(self):
        return f'{self.user_id} ← {self.message_id}'


class EntryGuideline(models.Model):
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='entry_guidelines',
    )
    name = models.CharField(max_length=255)
    pdf_file = models.FileField(upload_to='entry_guidelines/')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_entry_guidelines',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Entry guidelines'

    def __str__(self):
        return self.name


class GuidelineDispatch(models.Model):
    guideline = models.ForeignKey(
        EntryGuideline,
        on_delete=models.CASCADE,
        related_name='dispatches',
    )
    sent_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_guideline_dispatches',
    )
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sent_at']
        verbose_name_plural = 'Guideline dispatches'

    def __str__(self):
        return f'{self.guideline.name} ({self.sent_at:%d.%m.%Y})'


class GuidelineDispatchRecipient(models.Model):
    KIND_SECTION = 'section'
    KIND_WORKER = 'worker'

    KIND_CHOICES = [
        (KIND_SECTION, 'Bo‘lim'),
        (KIND_WORKER, 'Xodim'),
    ]

    dispatch = models.ForeignKey(
        GuidelineDispatch,
        on_delete=models.CASCADE,
        related_name='recipients',
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='guideline_dispatch_receipts',
    )
    section = models.ForeignKey(
        Section,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='guideline_recipients',
    )
    recipient_kind = models.CharField(max_length=16, choices=KIND_CHOICES)
    is_acknowledged = models.BooleanField(default=False)
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['section__name', 'user__profile__full_name']
        constraints = [
            models.UniqueConstraint(fields=['dispatch', 'user'], name='unique_guideline_recipient_per_dispatch'),
        ]
        verbose_name_plural = 'Guideline dispatch recipients'

    def __str__(self):
        return f'{self.user_id} ← {self.dispatch_id}'


class SectionInternalGuideline(models.Model):
    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name='internal_guidelines',
    )
    name = models.CharField(max_length=255)
    pdf_file = models.FileField(upload_to='section_internal_guidelines/')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_section_internal_guidelines',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Section internal guidelines'

    def __str__(self):
        return self.name


class SectionInternalGuidelineDispatch(models.Model):
    guideline = models.ForeignKey(
        SectionInternalGuideline,
        on_delete=models.CASCADE,
        related_name='dispatches',
    )
    sent_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_section_internal_guideline_dispatches',
    )
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sent_at']
        verbose_name_plural = 'Section internal guideline dispatches'

    def __str__(self):
        return f'{self.guideline.name} ({self.sent_at:%d.%m.%Y})'


class SectionInternalGuidelineRecipient(models.Model):
    dispatch = models.ForeignKey(
        SectionInternalGuidelineDispatch,
        on_delete=models.CASCADE,
        related_name='recipients',
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='section_internal_guideline_receipts',
    )
    is_acknowledged = models.BooleanField(default=False)
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['user__profile__full_name', 'user__username']
        constraints = [
            models.UniqueConstraint(
                fields=['dispatch', 'user'],
                name='unique_section_internal_guideline_recipient_per_dispatch',
            ),
        ]
        verbose_name_plural = 'Section internal guideline recipients'

    def __str__(self):
        return f'{self.user_id} ← {self.dispatch_id}'


class SectionWorkPractice(models.Model):
    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name='work_practices',
    )
    name = models.CharField(max_length=255)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_work_practices',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_time', '-created_at']
        verbose_name_plural = 'Section work practices'

    def __str__(self):
        return self.name


class SectionWorkPracticeAssignee(models.Model):
    practice = models.ForeignKey(
        SectionWorkPractice,
        on_delete=models.CASCADE,
        related_name='assignees',
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='work_practice_assignments',
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['practice', 'user'],
                name='unique_work_practice_assignee',
            ),
        ]
        verbose_name_plural = 'Section work practice assignees'

    def __str__(self):
        return f'{self.user_id} → {self.practice_id}'
