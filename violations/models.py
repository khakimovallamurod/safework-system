from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class ViolationType(models.Model):
    name = models.CharField(max_length=255, verbose_name="Qoidabuzarlik turi nomi")

    class Meta:
        db_table = 'qoidabuzarlik_turi'
        verbose_name = 'Qoidabuzarlik turi'
        verbose_name_plural = 'Qoidabuzarlik turlari'

    def __str__(self):
        return self.name

class Violation(models.Model):
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='violations', verbose_name="Xodim")
    issued_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='issued_violations', verbose_name="Kiritgan nazoratchi")
    violation_type = models.ForeignKey(ViolationType, on_delete=models.CASCADE, verbose_name="Qoidabuzarlik turi")
    reason = models.TextField(verbose_name="Sabab (Izoh)")
    date = models.DateField(default=timezone.now, verbose_name="Sana")
    image = models.ImageField(upload_to='violations/', null=True, blank=True, verbose_name="Qoidabuzarlik rasmi")
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True, verbose_name="Faolmi (Tushuntirish xati olinmagan)")

    class Meta:
        ordering = ['-date', '-created_at']
        db_table = 'qoidabuzarlik'
        verbose_name = 'Qoidabuzarlik'
        verbose_name_plural = 'Qoidabuzarliklar'

    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.violation_type.name} ({self.date})"


class ExplanationLetter(models.Model):
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='explanation_letters', verbose_name="Xodim")
    unblocked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='unblocked_employees', verbose_name="Blokdan chiqargan shaxs")
    explanation_text = models.TextField(verbose_name="Izoh (Tushuntirish)")
    file = models.FileField(upload_to='explanation_letters/', verbose_name="Tushuntirish xati (PDF/Rasm)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        db_table = 'tushuntirish_xati'
        verbose_name = 'Tushuntirish xati'
        verbose_name_plural = 'Tushuntirish xatlari'

    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.created_at.strftime('%Y-%m-%d')}"
