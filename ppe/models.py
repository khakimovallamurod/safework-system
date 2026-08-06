from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class PPEType(models.Model):
    organization = models.ForeignKey('accounts.UserProfile', on_delete=models.CASCADE, null=True, blank=True, related_name='ppe_types', verbose_name="Tashkilot")
    name = models.CharField(max_length=255, verbose_name="IHV turi")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'ppe_type'
        verbose_name = 'IHV Turi'
        verbose_name_plural = 'IHV Turlari'
        ordering = ['name']

    def __str__(self):
        return self.name


class PPEIssue(models.Model):
    CONDITION_CHOICES = [
        ('alo', "A'lo"),
        ('yaxshi', "Yaxshi"),
        ('qoniqarli', "Qoniqarli"),
        ('yaroqsiz', "Yaroqsiz"),
    ]
    
    STATUS_CHOICES = [
        ('pending', "Kutilmoqda"),
        ('accepted', "Qabul qilindi"),
    ]

    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ppe_issues', verbose_name="Xodim")
    ppe_type = models.ForeignKey(PPEType, on_delete=models.CASCADE, related_name='issues', verbose_name="IHV Turi")
    issued_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='issued_ppes', verbose_name="Beruvchi")
    issue_date = models.DateField(verbose_name="Berilgan sana")
    expiration_date = models.DateField(verbose_name="Amal qilish muddati")
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, verbose_name="Holati")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Status")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Tahrirlangan sana")
    acknowledged_at = models.DateTimeField(null=True, blank=True, verbose_name="Qabul qilingan vaqt")

    class Meta:
        db_table = 'ppe_issue'
        verbose_name = 'IHV Berish'
        verbose_name_plural = 'IHV Berilganlar'
        ordering = ['-issue_date', '-created_at']

    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.ppe_type.name}"
