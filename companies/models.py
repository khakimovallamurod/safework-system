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
    is_password_viewed = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Companies'
        db_table = 'tashkilot'

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
        self.is_active = False
        self.save(update_fields=['is_active'])
        if self.user:
            self.user.is_active = False
            self.user.save(update_fields=['is_active'])

    def regenerate_password(self):
        new_pass = self._generate_password()
        self.password = new_pass
        self.is_password_viewed = False
        self.save(update_fields=['password', 'is_password_viewed'])
        if self.user:
            self.user.set_password(new_pass)
            self.user.save(update_fields=['password'])
            
    def mark_password_viewed(self):
        self.password = ''
        self.is_password_viewed = True
        self.save(update_fields=['password', 'is_password_viewed'])


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
        db_table = 'boshqarma'

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
        db_table = 'bolim'

    def __str__(self):
        return self.name


class SectionMembership(models.Model):
    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name='memberships',
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='section_memberships',
    )
    profession = models.ForeignKey(
        'professions.Profession',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='section_memberships',
        verbose_name='Kasb',
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-assigned_at']
        verbose_name_plural = 'Section memberships'
        db_table = 'azo'
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
        db_table = 'xabar'

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
        db_table = 'xabar_holat'

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
        db_table = 'kirish_nizom'

    def __str__(self):
        return self.name

    @property
    def pdf_file_exists(self):
        if not self.pdf_file:
            return False
        return self.pdf_file.storage.exists(self.pdf_file.name)


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
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-sent_at']
        verbose_name_plural = 'Guideline dispatches'
        db_table = 'nizom_yuborish'

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
        db_table = 'nizom_qabul'
        constraints = [
            models.UniqueConstraint(fields=['dispatch', 'user'], name='unique_guideline_recipient_per_dispatch'),
        ]
        verbose_name_plural = 'Guideline dispatch recipients'

    def __str__(self):
        return f'{self.user_id} ← {self.dispatch_id}'


class MandatoryGuideline(models.Model):
    TYPE_MEDICAL = 'medical'
    TYPE_FIRE = 'fire'
    TYPE_ELECTRIC = 'electric'

    TYPE_CHOICES = [
        (TYPE_MEDICAL, 'Tibbiy yordam yo‘riqnomasi'),
        (TYPE_FIRE, "Yong'in xavfsizligi yo‘riqnomasi"),
        (TYPE_ELECTRIC, 'Elektr xavfsizligi yo‘riqnomasi'),
    ]

    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='mandatory_guidelines',
    )
    guideline_type = models.CharField(max_length=24, choices=TYPE_CHOICES)
    name = models.CharField(max_length=255)
    pdf_file = models.FileField(upload_to='mandatory_guidelines/')
    start_time = models.DateTimeField(verbose_name='Boshlanish vaqti')
    active_until = models.DateTimeField(verbose_name='Faollik tugashi')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_mandatory_guidelines',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['guideline_type', '-created_at']
        db_table = 'majburiy_yoriqnoma'
        unique_together = ('department', 'guideline_type')

    def __str__(self):
        return self.name

    @property
    def pdf_file_exists(self):
        if not self.pdf_file:
            return False
        return self.pdf_file.storage.exists(self.pdf_file.name)

    @property
    def is_currently_active(self):
        now = timezone.now()
        return self.start_time <= now <= self.active_until

    @property
    def days_left(self):
        if not self.active_until:
            return None
        now = timezone.now()
        delta = self.active_until - now
        return delta.days if delta.days >= 0 else -1


class MandatoryGuidelineReceipt(models.Model):
    guideline = models.ForeignKey(
        MandatoryGuideline,
        on_delete=models.CASCADE,
        related_name='receipts',
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='mandatory_guideline_receipts',
    )
    is_acknowledged = models.BooleanField(default=False)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['guideline__guideline_type', 'user__profile__full_name']
        db_table = 'majburiy_yoriqnoma_qabul'
        constraints = [
            models.UniqueConstraint(fields=['guideline', 'user'], name='unique_mandatory_guideline_receipt'),
        ]

    def __str__(self):
        return f'{self.user_id} ← {self.guideline_id}'


class ProfessionGuidelineReceipt(models.Model):
    membership = models.OneToOneField(
        SectionMembership,
        on_delete=models.CASCADE,
        related_name='profession_guideline_receipt',
    )
    profession = models.ForeignKey(
        'professions.Profession',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='guideline_receipts',
    )
    is_acknowledged = models.BooleanField(default=False)
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'kasb_yoriqnoma_qabul'

    @property
    def can_open(self):
        if not self.profession:
            return False
        return self.profession.is_currently_active

    def __str__(self):
        return f'{self.membership.user_id} ← {self.membership.profession_id}'


class EmployeeMedicalRecord(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='medical_records',
        verbose_name='Xodim',
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='medical_records',
        verbose_name='Boshqarma',
    )
    section = models.ForeignKey(
        Section,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='medical_records',
        verbose_name="Bo'lim",
    )
    profession = models.ForeignKey(
        'professions.Profession',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='medical_records',
        verbose_name='Kasb',
    )
    start_date = models.DateField(verbose_name='Boshlanish sana')
    end_date = models.DateField(verbose_name='Tugash sana')
    file = models.FileField(upload_to='medical_records/', null=True, blank=True, verbose_name='Fayl')
    note = models.TextField(blank=True, verbose_name='Izoh')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_medical_records',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['end_date', 'user__profile__full_name']
        db_table = 'tibbiy_malumot'

    def __str__(self):
        return f'{self.user_id} · {self.end_date:%d.%m.%Y}'

    @property
    def days_left(self):
        return (self.end_date - timezone.localdate()).days

    @property
    def status_key(self):
        days = self.days_left
        if days <= 7:
            return 'danger'
        if days <= 30:
            return 'warning'
        return 'ok'

    @property
    def status_label(self):
        if self.days_left < 0:
            return "Muddati o'tgan"
        if self.status_key == 'danger':
            return 'Tugash arafasida'
        if self.status_key == 'warning':
            return 'Yaqinlashmoqda'
        return 'Faol'


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
    start_time = models.DateTimeField(null=True, blank=True, verbose_name='Boshlanish vaqti')
    registration_end_time = models.DateTimeField(null=True, blank=True, verbose_name="Ro'yxatdan o'tish oxiri")
    active_until = models.DateTimeField(null=True, blank=True, verbose_name='Faollik tugashi')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Section internal guidelines'
        db_table = 'ichki_nizom'

    def __str__(self):
        return self.name

    @property
    def pdf_file_exists(self):
        if not self.pdf_file:
            return False
        return self.pdf_file.storage.exists(self.pdf_file.name)


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
    is_active = models.BooleanField(default=False, verbose_name='Faol')
    start_time = models.DateTimeField(null=True, blank=True, verbose_name='Boshlanish vaqti')
    registration_end_time = models.DateTimeField(null=True, blank=True, verbose_name="Ro'yxatdan o'tish oxiri")
    active_until = models.DateTimeField(null=True, blank=True, verbose_name='Faollik tugashi')
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sent_at']
        verbose_name_plural = 'Section internal guideline dispatches'
        db_table = 'ichki_nizom_yuborish'

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
        db_table = 'ichki_nizom_qabul'
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
    responsible_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='responsible_work_practices',
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_work_practices',
    )
    closed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='closed_work_practices',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_time', '-created_at']
        verbose_name_plural = 'Section work practices'
        db_table = 'ish_amaliyot'

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
    accepted_by_responsible = models.BooleanField(default=False)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'ish_amaliyot_azo'
        constraints = [
            models.UniqueConstraint(
                fields=['practice', 'user'],
                name='unique_work_practice_assignee',
            ),
        ]
        verbose_name_plural = 'Section work practice assignees'

    def __str__(self):
        return f'{self.user_id} → {self.practice_id}'


class SectionWorkPracticeMessage(models.Model):
    practice = models.ForeignKey(
        SectionWorkPractice,
        on_delete=models.CASCADE,
        related_name='practice_messages',
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_work_practice_messages',
    )
    title = models.CharField(max_length=255)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        db_table = 'amaliyot_xabar'
        verbose_name_plural = 'Work practice messages'

    def __str__(self):
        return self.title


class SectionWorkPracticeMessageReceipt(models.Model):
    message = models.ForeignKey(
        SectionWorkPracticeMessage,
        on_delete=models.CASCADE,
        related_name='receipts',
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='work_practice_message_receipts',
    )
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'amaliyot_xabar_holat'
        constraints = [
            models.UniqueConstraint(
                fields=['message', 'user'],
                name='unique_work_practice_message_recipient',
            ),
        ]
        verbose_name_plural = 'Work practice message receipts'

    def __str__(self):
        return f'{self.user_id} ← {self.message_id}'


class WorkPracticeTest(models.Model):
    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name='practice_tests'
    )
    name = models.CharField(max_length=255, verbose_name="Test nomi")
    duration = models.PositiveIntegerField(verbose_name="Davomiyligi (daqiqa)")
    attempts_allowed = models.PositiveIntegerField(verbose_name="Urinishlar soni")
    questions_count = models.PositiveIntegerField(verbose_name="Savollar soni")
    is_active = models.BooleanField(default=True, verbose_name="Status")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        db_table = 'amaliyot_test'
        verbose_name_plural = 'Work practice tests'

    def __str__(self):
        return self.name


class WorkPracticeTestQuestion(models.Model):
    test = models.ForeignKey(
        WorkPracticeTest,
        on_delete=models.CASCADE,
        related_name='questions'
    )
    text = models.TextField(verbose_name="Savol matni")
    option_1 = models.CharField(max_length=255, verbose_name="1-variant")
    option_2 = models.CharField(max_length=255, verbose_name="2-variant")
    option_3 = models.CharField(max_length=255, verbose_name="3-variant")
    correct_option = models.IntegerField(
        choices=[(1, '1-variant'), (2, '2-variant'), (3, '3-variant')],
        verbose_name="To'g'ri variant"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        db_table = 'amaliyot_test_savol'
        verbose_name_plural = 'Work practice test questions'

    def __str__(self):
        return f"Savol {self.id}"


class WorkPracticeTestAttempt(models.Model):
    practice = models.ForeignKey(
        SectionWorkPractice,
        on_delete=models.CASCADE,
        related_name='test_attempts'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='practice_test_attempts'
    )
    test = models.ForeignKey(
        WorkPracticeTest,
        on_delete=models.CASCADE,
        related_name='attempts'
    )
    score = models.IntegerField(null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']
        db_table = 'amaliyot_test_urinish'
        verbose_name_plural = 'Work practice test attempts'

    def __str__(self):
        return f"{self.user} - {self.test.name} ({self.score})"


class WorkPracticeTestPermission(models.Model):
    """Test qaysi ish amaliyotlariga ruxsat berilganligi"""
    test = models.ForeignKey(
        WorkPracticeTest,
        on_delete=models.CASCADE,
        related_name='practice_permissions'
    )
    practice = models.ForeignKey(
        SectionWorkPractice,
        on_delete=models.CASCADE,
        related_name='test_permissions'
    )

    class Meta:
        unique_together = ['test', 'practice']
        db_table = 'amaliyot_test_ruxsat'
        verbose_name_plural = 'Work practice test permissions'

    def __str__(self):
        return f"{self.test.name} → {self.practice.name}"


class WorkPracticeTestAttemptAnswer(models.Model):
    attempt = models.ForeignKey(
        WorkPracticeTestAttempt,
        on_delete=models.CASCADE,
        related_name='answers'
    )
    question = models.ForeignKey(
        WorkPracticeTestQuestion,
        on_delete=models.CASCADE
    )
    selected_option = models.IntegerField()
    is_correct = models.BooleanField()

    class Meta:
        unique_together = ['attempt', 'question']
        db_table = 'amaliyot_test_javob'


# ─────────────────────────────────────────────────────────────
#  BOSHQARMA DARAJASIDAGI BILIMNI BAHOLASH (Department Assessment)
# ─────────────────────────────────────────────────────────────

class DepartmentTestBaseQuestion(models.Model):
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name='test_base_questions',
    )
    text = models.TextField(verbose_name="Savol matni")
    option_1 = models.CharField(max_length=500, verbose_name="A variant")
    option_2 = models.CharField(max_length=500, verbose_name="B variant")
    option_3 = models.CharField(max_length=500, verbose_name="C variant")
    correct_option = models.IntegerField(
        choices=[(1, 'A'), (2, 'B'), (3, 'C')],
        verbose_name="To'g'ri variant",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        db_table = 'boshqarma_test_bazasi_savol'

    def __str__(self):
        return f"Savol {self.id} — {self.department.name}"


class DepartmentAssessment(models.Model):
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='assessments',
        verbose_name="Boshqarma",
    )
    name = models.CharField(max_length=255, verbose_name="Test nomi")
    duration = models.PositiveIntegerField(verbose_name="Davomiyligi (daqiqa)")
    questions_count = models.PositiveIntegerField(verbose_name="Savollar soni")
    attempts_allowed = models.PositiveIntegerField(default=1, verbose_name="Urinishlar soni")
    notes = models.TextField(blank=True, verbose_name="Izoh")
    is_active = models.BooleanField(default=False, verbose_name="Faol")
    is_published = models.BooleanField(default=False, verbose_name="Joriy qilingan")
    published_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='created_assessments',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        db_table = 'boshqarma_baholash'
        verbose_name_plural = 'Department assessments'

    def __str__(self):
        return self.name

    @property
    def question_count_ok(self):
        return self.questions.count() >= self.questions_count


class DepartmentAssessmentQuestion(models.Model):
    assessment = models.ForeignKey(
        DepartmentAssessment, on_delete=models.CASCADE, related_name='questions',
    )
    text = models.TextField(verbose_name="Savol matni")
    option_1 = models.CharField(max_length=500, verbose_name="A variant")
    option_2 = models.CharField(max_length=500, verbose_name="B variant")
    option_3 = models.CharField(max_length=500, verbose_name="C variant")
    correct_option = models.IntegerField(
        choices=[(1, 'A'), (2, 'B'), (3, 'C')],
        verbose_name="To'g'ri variant",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        db_table = 'boshqarma_baholash_savol'

    def __str__(self):
        return f"Savol {self.id} — {self.assessment.name}"


class DepartmentAssessmentNotification(models.Model):
    assessment = models.ForeignKey(
        DepartmentAssessment, on_delete=models.CASCADE, related_name='notifications',
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='dept_assessment_notifications',
    )
    is_confirmed = models.BooleanField(default=False)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['assessment', 'user']
        db_table = 'boshqarma_baholash_xabar'

    def __str__(self):
        return f"{self.assessment.name} → {self.user}"


class DepartmentAssessmentAttempt(models.Model):
    assessment = models.ForeignKey(
        DepartmentAssessment, on_delete=models.CASCADE, related_name='attempts',
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='dept_assessment_attempts',
    )
    score = models.IntegerField(null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']
        db_table = 'boshqarma_baholash_urinish'

    def __str__(self):
        return f"{self.user} — {self.assessment.name} ({self.score}%)"


class DepartmentAssessmentAttemptAnswer(models.Model):
    attempt = models.ForeignKey(
        DepartmentAssessmentAttempt, on_delete=models.CASCADE, related_name='dept_answers',
    )
    question = models.ForeignKey(DepartmentAssessmentQuestion, on_delete=models.CASCADE)
    selected_option = models.IntegerField()
    is_correct = models.BooleanField()

    class Meta:
        unique_together = ['attempt', 'question']
        db_table = 'boshqarma_baholash_javob'


class WorkerTransferHistory(models.Model):
    worker = models.ForeignKey('accounts.UserProfile', on_delete=models.CASCADE, related_name='transfer_history', limit_choices_to={'role': 'worker'})
    from_section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True, related_name='transfers_out')
    to_section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True, related_name='transfers_in')
    transferred_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='performed_transfers')
    transferred_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(blank=True)

    class Meta:
        ordering = ['-transferred_at']
        db_table = 'worker_transfer_history'
        verbose_name_plural = 'Worker transfer histories'

    def __str__(self):
        return f"{self.worker} transferred on {self.transferred_at}"


class CertificateType(models.Model):
    name = models.CharField(max_length=255, verbose_name="Sertifikat turi nomi")
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_certificate_types',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        db_table = 'sertifikat_turi'
        verbose_name_plural = 'Certificate Types'

    def __str__(self):
        return self.name


class EmployeeCertificate(models.Model):
    certificate_type = models.ForeignKey(
        CertificateType,
        on_delete=models.CASCADE,
        related_name='employee_certificates',
        verbose_name="Sertifikat turi"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='certificates',
        verbose_name="Xodim"
    )
    file = models.FileField(upload_to='certificates/', verbose_name="Sertifikat (PDF)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yuklangan sana")

    class Meta:
        ordering = ['-created_at']
        db_table = 'xodim_sertifikati'
        verbose_name_plural = 'Employee Certificates'

    def __str__(self):
        return f"{self.user} - {self.certificate_type.name}"
