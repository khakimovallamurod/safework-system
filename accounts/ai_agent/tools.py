import json
import logging
from django.db.models import Q, Count
from django.utils import timezone
from .rag import get_retriever

logger = logging.getLogger(__name__)


class SoplineDataTools:
    """
    Sopline System ma'lumotlar bazasi va RAG me'yoriy hujjatlar qidiruvi uchun AI Agent Tools.
    Barcha vositalar foydalanuvchining roli va tashkilotiga qat'iy cheklangan holda (RBAC) ishlaydi.
    """

    def __init__(self, user, role_context):
        self.user = user
        self.role_context = role_context
        self.profile = getattr(user, 'profile', None)
        self.role = getattr(self.profile, 'role', 'worker')
        self.is_super_admin = user.is_superuser or self.role == 'super_admin'

    def _get_org_filter(self):
        """Foydalanuvchining tashkilot ID sini aniqlash"""
        if self.is_super_admin:
            return None
        if not self.profile:
            return -1
        if self.role == 'organization_leader':
            return self.profile.id
        return self.profile.organization_id or getattr(self.profile.organization, 'id', -1)

    # 1. RAG Tool: Me'yoriy hujjatlar va qoidalar bo'yicha qidiruv
    def search_safety_documents(self, query=None, **kwargs):
        """
        RAG Qidiruv: Mehnat muhofazasi qonunlari, yong'in, elektr, birinchi yordam,
        IHV, balandlikda ishlash va texnika xavfsizligi bo'yicha me'yoriy hujjatlardan qidiradi.
        """
        if not query:
            return {"error": "Qidiruv so'rovi kiritilmadi."}

        try:
            retriever = get_retriever()
            results = retriever.search(query, top_k=3)
            if not results:
                return {
                    "query": query,
                    "found_count": 0,
                    "message": "Me'yoriy hujjatlardan ushbu so'rov bo'yicha aniq ma'lumot topilmadi."
                }

            return {
                "query": query,
                "found_count": len(results),
                "citations": [
                    {
                        "document": r["doc_name"],
                        "relevance_score": r["score"],
                        "content": r["text"]
                    }
                    for r in results
                ]
            }
        except Exception as e:
            logger.exception("RAG search error")
            return {"error": f"Hujjatlarni qidirishda xatolik yuz berdi: {str(e)}"}

    # 2. Foydalanuvchi profili va huquqlari
    def get_user_profile_and_permissions(self, **kwargs):
        """
        Joriy foydalanuvchining roli, vakolatlari, tashkilot nomi, lavozimi va holatini qaytaradi.
        """
        if not self.profile:
            return {
                "user": self.user.username,
                "role": "Super Admin" if self.user.is_superuser else "Mehmon",
                "permissions": "Barcha tizimni boshqarish" if self.user.is_superuser else "Cheklangan"
            }

        data = {
            "full_name": self.profile.full_name or self.user.get_full_name() or self.user.username,
            "username": self.user.username,
            "role": self.profile.get_role_display(),
            "role_code": self.role,
            "organization": self.profile.organization_name or (self.profile.organization.organization_name if self.profile.organization else "-"),
            "department": self.profile.department.name if self.profile.department else "-",
            "section": self.profile.section.name if self.profile.section else "-",
            "position": self.profile.position or "-",
            "phone_number": self.profile.phone_number or "-",
            "practice_qualified": self.profile.practice_qualified,
            "assessment_qualified": self.profile.assessment_qualified,
            "is_blocked": self.profile.is_blocked_by_violations
        }
        return data

    # 3. Tashkilot tuzilmasi
    def get_organization_and_structure_info(self, **kwargs):
        """
        Tashkilot tuzilmasi: boshqarmalar, bo'limlar, ularning rahbarlari va mas'ullari haqida ma'lumot beradi.
        """
        from companies.models import Department, Section
        org_id = self._get_org_filter()
        departments_qs = Department.objects.all().select_related('leader', 'supervisor')
        sections_qs = Section.objects.all().select_related('department')

        if not self.is_super_admin:
            if self.role == 'organization_leader':
                departments_qs = departments_qs.filter(leader_id=org_id)
                sections_qs = sections_qs.filter(department__leader_id=org_id)
            elif self.role == 'department_admin' and self.profile and self.profile.department_id:
                departments_qs = departments_qs.filter(id=self.profile.department_id)
                sections_qs = sections_qs.filter(department_id=self.profile.department_id)
            elif self.role in ['section_admin', 'worker'] and self.profile and self.profile.section_id:
                sections_qs = sections_qs.filter(id=self.profile.section_id)
                departments_qs = departments_qs.filter(sections__id=self.profile.section_id).distinct()
            else:
                return {"message": "Sizga biriktirilgan boshqarma yoki bo'lim topilmadi."}

        dept_list = []
        for d in departments_qs[:15]:
            dept_sections = sections_qs.filter(department=d)
            dept_list.append({
                "id": d.id,
                "name": d.name,
                "supervisor": d.supervisor.get_full_name() or d.supervisor.username if d.supervisor else "Tayinlanmagan",
                "sections_count": dept_sections.count(),
                "sections": [s.name for s in dept_sections[:10]]
            })

        return {
            "total_departments": departments_qs.count(),
            "total_sections": sections_qs.count(),
            "departments": dept_list
        }

    # 4. Xodimlar ro'yxati va statistikasi
    def get_workers_summary(self, query=None, department_name=None, section_name=None, **kwargs):
        """
        Xodimlar ro'yxati, soni, bo'limi, lavozimi, bloklanganlik va malaka holati bo'yicha ma'lumot beradi.
        """
        from accounts.models import UserProfile
        org_id = self._get_org_filter()
        qs = UserProfile.objects.all().select_related('user', 'department', 'section')

        if not self.is_super_admin:
            if self.role == 'organization_leader':
                qs = qs.filter(Q(organization_id=org_id) | Q(id=org_id))
            elif self.role == 'department_admin' and self.profile and self.profile.department_id:
                qs = qs.filter(department_id=self.profile.department_id)
            elif self.role == 'section_admin' and self.profile and self.profile.section_id:
                qs = qs.filter(section_id=self.profile.section_id)
            else:
                if self.profile and self.profile.section_id:
                    qs = qs.filter(section_id=self.profile.section_id)
                else:
                    qs = qs.filter(user=self.user)

        if query:
            qs = qs.filter(
                Q(full_name__icontains=query) |
                Q(position__icontains=query) |
                Q(phone_number__icontains=query) |
                Q(user__username__icontains=query)
            )

        if department_name:
            qs = qs.filter(department__name__icontains=department_name)
        if section_name:
            qs = qs.filter(section__name__icontains=section_name)

        total_count = qs.count()
        blocked_count = qs.filter(is_blocked_by_violations=True).count()
        qualified_practice = qs.filter(practice_qualified_status=True).count()

        workers_sample = []
        for p in qs[:20]:
            workers_sample.append({
                "name": p.full_name or p.user.username,
                "role": p.get_role_display(),
                "position": p.position or "-",
                "department": p.department.name if p.department else "-",
                "section": p.section.name if p.section else "-",
                "phone": p.phone_number or "-",
                "is_blocked": p.is_blocked_by_violations,
                "practice_passed": p.practice_qualified
            })

        return {
            "total_workers": total_count,
            "blocked_count": blocked_count,
            "qualified_practice_count": qualified_practice,
            "workers": workers_sample
        }

    # 5. Qoidabuzarliklar statistikasi
    def get_violations_and_compliance(self, worker_name=None, only_active=True, **kwargs):
        """
        Mehnat muhofazasi qoidabuzarliklari, ogohlantirishlar, sabablari va muddatlari haqida ma'lumot beradi.
        """
        from violations.models import Violation
        org_id = self._get_org_filter()
        violations_qs = Violation.objects.all().select_related('employee', 'issued_by', 'violation_type', 'employee__profile')

        if not self.is_super_admin:
            if self.role == 'organization_leader':
                violations_qs = violations_qs.filter(
                    Q(employee__profile__organization_id=org_id) | Q(employee__profile__id=org_id)
                )
            elif self.role == 'department_admin' and self.profile and self.profile.department_id:
                violations_qs = violations_qs.filter(employee__profile__department_id=self.profile.department_id)
            elif self.role == 'section_admin' and self.profile and self.profile.section_id:
                violations_qs = violations_qs.filter(employee__profile__section_id=self.profile.section_id)
            else:
                violations_qs = violations_qs.filter(employee=self.user)

        if worker_name:
            violations_qs = violations_qs.filter(
                Q(employee__profile__full_name__icontains=worker_name) |
                Q(employee__username__icontains=worker_name)
            )

        if only_active:
            violations_qs = violations_qs.filter(is_active=True)

        total_violations = violations_qs.count()
        recent_items = []
        for v in violations_qs[:15]:
            emp_p = getattr(v.employee, 'profile', None)
            recent_items.append({
                "worker": emp_p.full_name if emp_p and emp_p.full_name else v.employee.username,
                "type": v.violation_type.name if v.violation_type else "Umumiy",
                "date": str(v.date),
                "reason": v.reason,
                "issued_by": v.issued_by.get_full_name() or v.issued_by.username if v.issued_by else "-",
                "is_active": v.is_active
            })

        return {
            "total_violations_found": total_violations,
            "recent_violations": recent_items
        }

    # 6. Tushuntirish xatlari
    def get_explanation_letters(self, worker_name=None, **kwargs):
        """
        Qoidabuzarlik sodir etgan xodimlar tomonidan topshirilgan tushuntirish xatlari va blokdan chiqarilish holati.
        """
        from violations.models import ExplanationLetter
        org_id = self._get_org_filter()
        qs = ExplanationLetter.objects.all().select_related('employee', 'unblocked_by', 'employee__profile')

        if not self.is_super_admin:
            if self.role == 'organization_leader':
                qs = qs.filter(
                    Q(employee__profile__organization_id=org_id) | Q(employee__profile__id=org_id)
                )
            elif self.role == 'department_admin' and self.profile and self.profile.department_id:
                qs = qs.filter(employee__profile__department_id=self.profile.department_id)
            elif self.role == 'section_admin' and self.profile and self.profile.section_id:
                qs = qs.filter(employee__profile__section_id=self.profile.section_id)
            else:
                qs = qs.filter(employee=self.user)

        if worker_name:
            qs = qs.filter(
                Q(employee__profile__full_name__icontains=worker_name) |
                Q(employee__username__icontains=worker_name)
            )

        letters = []
        for l in qs[:10]:
            emp_p = getattr(l.employee, 'profile', None)
            letters.append({
                "worker": emp_p.full_name if emp_p and emp_p.full_name else l.employee.username,
                "text": l.explanation_text[:150] + "..." if len(l.explanation_text) > 150 else l.explanation_text,
                "unblocked_by": l.unblocked_by.get_full_name() or l.unblocked_by.username if l.unblocked_by else "Kutilmoqda",
                "date": str(l.created_at.date()) if l.created_at else "-"
            })

        return {
            "total_letters": qs.count(),
            "letters": letters
        }

    # 7. Shaxsiy himoya vositalari (IHV / PPE)
    def get_ppe_safety_equipment_info(self, status=None, **kwargs):
        """
        Shaxsiy himoya vositalari (IHV / PPE), berilgan vositalar, muddatlari va qabul qilish holati.
        """
        from ppe.models import PPEIssue
        org_id = self._get_org_filter()
        issues_qs = PPEIssue.objects.all().select_related('employee', 'ppe_type', 'employee__profile')

        if not self.is_super_admin:
            if self.role == 'organization_leader':
                issues_qs = issues_qs.filter(
                    Q(employee__profile__organization_id=org_id) | Q(employee__profile__id=org_id)
                )
            elif self.role == 'department_admin' and self.profile and self.profile.department_id:
                issues_qs = issues_qs.filter(employee__profile__department_id=self.profile.department_id)
            elif self.role == 'section_admin' and self.profile and self.profile.section_id:
                issues_qs = issues_qs.filter(employee__profile__section_id=self.profile.section_id)
            else:
                issues_qs = issues_qs.filter(employee=self.user)

        if status:
            issues_qs = issues_qs.filter(status=status)

        today = timezone.now().date()
        expired_count = issues_qs.filter(expiration_date__lt=today).count()
        pending_count = issues_qs.filter(status='pending').count()
        accepted_count = issues_qs.filter(status='accepted').count()

        sample_issues = []
        for issue in issues_qs[:15]:
            emp_p = getattr(issue.employee, 'profile', None)
            sample_issues.append({
                "worker": emp_p.full_name if emp_p and emp_p.full_name else issue.employee.username,
                "ppe_name": issue.ppe_type.name,
                "issue_date": str(issue.issue_date),
                "expiration_date": str(issue.expiration_date),
                "status": issue.get_status_display() if hasattr(issue, 'get_status_display') else issue.status,
                "is_expired": bool(issue.expiration_date and issue.expiration_date < today)
            })

        return {
            "total_records": issues_qs.count(),
            "pending_acceptance": pending_count,
            "accepted": accepted_count,
            "expired_count": expired_count,
            "sample_issues": sample_issues
        }

    # 8. IHV Turlari katalogi
    def get_ppe_types_catalog(self, **kwargs):
        """
        Tizimda mavjud bo'lgan barcha Shaxsiy himoya vositalari (IHV) turlari va ularning yaroqlilik standartlari.
        """
        from ppe.models import PPEType
        qs = PPEType.objects.all()
        return {
            "total_types": qs.count(),
            "ppe_catalog": [
                {
                    "id": p.id,
                    "name": p.name,
                    "standard_period_months": getattr(p, 'standard_period_months', None) or 12
                }
                for p in qs[:25]
            ]
        }

    # 9. Yo'riqnomalar holati
    def get_guidelines_status(self, guideline_type="all", **kwargs):
        """
        Mehnat muhofazasi yo'riqnomalari: kirish, ichki, majburiy va kasbiy yo'riqnomalar va ularning qabul holati.
        """
        from companies.models import (
            EntryGuideline,
            MandatoryGuideline,
            SectionInternalGuideline,
            GuidelineDispatchRecipient
        )

        org_id = self._get_org_filter()
        results = {}

        if self.role == 'worker':
            recipients = GuidelineDispatchRecipient.objects.filter(user=self.user).select_related('dispatch__guideline')
            results["my_guidelines"] = [
                {
                    "name": r.dispatch.guideline.name if r.dispatch and r.dispatch.guideline else "-",
                    "acknowledged": r.is_acknowledged,
                    "acknowledged_at": str(r.acknowledged_at) if r.acknowledged_at else "-"
                }
                for r in recipients[:10]
            ]
            return results

        eg_qs = EntryGuideline.objects.all()
        mg_qs = MandatoryGuideline.objects.all()
        ig_qs = SectionInternalGuideline.objects.all()

        if not self.is_super_admin:
            if self.role == 'organization_leader':
                eg_qs = eg_qs.filter(department__leader_id=org_id)
                mg_qs = mg_qs.filter(department__leader_id=org_id)
                ig_qs = ig_qs.filter(section__department__leader_id=org_id)
            elif self.role == 'department_admin' and self.profile and self.profile.department_id:
                eg_qs = eg_qs.filter(department_id=self.profile.department_id)
                mg_qs = mg_qs.filter(department_id=self.profile.department_id)
                ig_qs = ig_qs.filter(section__department_id=self.profile.department_id)
            elif self.role == 'section_admin' and self.profile and self.profile.section_id:
                ig_qs = ig_qs.filter(section_id=self.profile.section_id)

        results["entry_guidelines_count"] = eg_qs.count()
        results["mandatory_guidelines_count"] = mg_qs.count()
        results["internal_guidelines_count"] = ig_qs.count()
        results["sample_guideline_names"] = list(eg_qs.values_list('name', flat=True)[:5]) + list(mg_qs.values_list('name', flat=True)[:5])

        return results

    # 10. Majburiy yo'riqnomalar tafsilotlari
    def get_mandatory_guidelines_details(self, guideline_type=None, **kwargs):
        """
        Majburiy yo'riqnomalar: tibbiy yordam, yong'in va elektr xavfsizligi bo'yicha maxsus ko'rsatmalar.
        """
        from companies.models import MandatoryGuideline
        org_id = self._get_org_filter()
        qs = MandatoryGuideline.objects.all().select_related('department')

        if not self.is_super_admin:
            if self.role == 'organization_leader':
                qs = qs.filter(department__leader_id=org_id)
            elif self.role == 'department_admin' and self.profile and self.profile.department_id:
                qs = qs.filter(department_id=self.profile.department_id)

        if guideline_type:
            qs = qs.filter(guideline_type=guideline_type)

        items = []
        for g in qs[:10]:
            items.append({
                "name": g.name,
                "type": g.get_guideline_type_display() if hasattr(g, 'get_guideline_type_display') else g.guideline_type,
                "department": g.department.name if g.department else "-",
                "active_until": str(g.active_until.date()) if g.active_until else "-"
            })

        return {
            "total_mandatory": qs.count(),
            "guidelines": items
        }

    # 11. Ish amaliyotlari (stajirovka)
    def get_practices_and_assessments(self, **kwargs):
        """
        Ish amaliyotlari (stajirovka), ularning mas'ullari, muddatlari va holati haqida ma'lumot beradi.
        """
        from companies.models import SectionWorkPractice
        org_id = self._get_org_filter()
        practice_qs = SectionWorkPractice.objects.all().select_related('section', 'responsible_user')

        if not self.is_super_admin:
            if self.role == 'organization_leader':
                practice_qs = practice_qs.filter(section__department__leader_id=org_id)
            elif self.role == 'department_admin' and self.profile and self.profile.department_id:
                practice_qs = practice_qs.filter(section__department_id=self.profile.department_id)
            elif self.role == 'section_admin' and self.profile and self.profile.section_id:
                practice_qs = practice_qs.filter(section_id=self.profile.section_id)
            else:
                practice_qs = practice_qs.filter(assignees__user=self.user)

        active_practices = practice_qs.filter(closed_at__isnull=True).count()
        completed_practices = practice_qs.filter(closed_at__isnull=False).count()

        practice_items = []
        for p in practice_qs[:10]:
            practice_items.append({
                "name": p.name,
                "section": p.section.name if p.section else "-",
                "responsible_user": p.responsible_user.get_full_name() or p.responsible_user.username if p.responsible_user else "-",
                "start": str(p.start_time.date()) if p.start_time else "-",
                "end": str(p.end_time.date()) if p.end_time else "-",
                "is_closed": p.closed_at is not None
            })

        return {
            "active_practices": active_practices,
            "completed_practices": completed_practices,
            "practices_sample": practice_items
        }

    # 12. Stajirovka test sinovlari natijalari
    def get_practice_test_results(self, worker_name=None, **kwargs):
        """
        Stajirovka va amaliyotlar bo'yicha xodimlarning topshirgan test natijalari, to'plangan ballar va urinishlar.
        """
        from companies.models import WorkPracticeTestAttempt
        org_id = self._get_org_filter()
        qs = WorkPracticeTestAttempt.objects.all().select_related('user', 'practice', 'test', 'user__profile')

        if not self.is_super_admin:
            if self.role == 'organization_leader':
                qs = qs.filter(practice__section__department__leader_id=org_id)
            elif self.role == 'department_admin' and self.profile and self.profile.department_id:
                qs = qs.filter(practice__section__department_id=self.profile.department_id)
            elif self.role == 'section_admin' and self.profile and self.profile.section_id:
                qs = qs.filter(practice__section_id=self.profile.section_id)
            else:
                qs = qs.filter(user=self.user)

        if worker_name:
            qs = qs.filter(
                Q(user__profile__full_name__icontains=worker_name) |
                Q(user__username__icontains=worker_name)
            )

        attempts = []
        for a in qs[:10]:
            emp_p = getattr(a.user, 'profile', None)
            attempts.append({
                "worker": emp_p.full_name if emp_p and emp_p.full_name else a.user.username,
                "test_name": a.test.name if a.test else "Amaliyot testi",
                "score": a.score,
                "finished_at": str(a.finished_at.date()) if a.finished_at else "Tugallanmagan"
            })

        return {
            "total_attempts": qs.count(),
            "results": attempts
        }

    # 13. Boshqarma bilim sinovlari va baholash (Department Assessment)
    def get_department_assessments(self, is_active=None, **kwargs):
        """
        Boshqarma miqyosidagi imtihonlar, bilim baholash testlari, davomiyligi va faol holati.
        """
        from companies.models import DepartmentAssessment
        org_id = self._get_org_filter()
        qs = DepartmentAssessment.objects.all().select_related('department')

        if not self.is_super_admin:
            if self.role == 'organization_leader':
                qs = qs.filter(department__leader_id=org_id)
            elif self.role == 'department_admin' and self.profile and self.profile.department_id:
                qs = qs.filter(department_id=self.profile.department_id)
            elif self.role in ['section_admin', 'worker'] and self.profile and self.profile.section_id:
                qs = qs.filter(target_sections__id=self.profile.section_id).distinct()

        if is_active is not None:
            qs = qs.filter(is_active=is_active)

        items = []
        for da in qs[:10]:
            items.append({
                "name": da.name,
                "department": da.department.name if da.department else "-",
                "duration_minutes": da.duration,
                "questions_count": da.questions_count,
                "is_active": da.is_active,
                "is_published": da.is_published
            })

        return {
            "total_assessments": qs.count(),
            "assessments": items
        }

    # 14. Tibbiy ko'riklar
    def get_medical_and_certificates_info(self, worker_name=None, **kwargs):
        """
        Xodimlarning tibbiy ko'rikdan o'tganlik holati va muddati o'tgan tibbiy ma'lumotnomalar.
        """
        from companies.models import EmployeeMedicalRecord
        today = timezone.now().date()
        med_qs = EmployeeMedicalRecord.objects.all().select_related('user', 'department', 'section', 'user__profile')

        if not self.is_super_admin:
            org_id = self._get_org_filter()
            if self.role == 'organization_leader':
                med_qs = med_qs.filter(department__leader_id=org_id)
            elif self.role == 'department_admin' and self.profile and self.profile.department_id:
                med_qs = med_qs.filter(department_id=self.profile.department_id)
            elif self.role == 'section_admin' and self.profile and self.profile.section_id:
                med_qs = med_qs.filter(section_id=self.profile.section_id)
            else:
                med_qs = med_qs.filter(user=self.user)

        if worker_name:
            med_qs = med_qs.filter(
                Q(user__profile__full_name__icontains=worker_name) | Q(user__username__icontains=worker_name)
            )

        expired_med = med_qs.filter(end_date__lt=today).count()
        sample_records = []
        for m in med_qs[:10]:
            p = getattr(m.user, 'profile', None)
            sample_records.append({
                "worker": p.full_name if p and p.full_name else m.user.username,
                "department": m.department.name if m.department else "-",
                "end_date": str(m.end_date),
                "is_expired": m.end_date < today
            })

        return {
            "total_medical_records": med_qs.count(),
            "expired_medical_records": expired_med,
            "sample_records": sample_records
        }

    # 15. Xodimlar kasbiy sertifikatlari
    def get_employee_certificates(self, worker_name=None, **kwargs):
        """
        Xodimlarning kasbiy malaka sertifikatlari, berilgan sanasi va sertifikat turlari.
        """
        from companies.models import EmployeeCertificate
        cert_qs = EmployeeCertificate.objects.all().select_related('user', 'certificate_type', 'user__profile')

        if not self.is_super_admin:
            org_id = self._get_org_filter()
            if self.role == 'organization_leader':
                cert_qs = cert_qs.filter(
                    Q(user__profile__organization_id=org_id) | Q(user__profile__id=org_id)
                )
            elif self.role == 'department_admin' and self.profile and self.profile.department_id:
                cert_qs = cert_qs.filter(user__profile__department_id=self.profile.department_id)
            elif self.role == 'section_admin' and self.profile and self.profile.section_id:
                cert_qs = cert_qs.filter(user__profile__section_id=self.profile.section_id)
            else:
                cert_qs = cert_qs.filter(user=self.user)

        if worker_name:
            cert_qs = cert_qs.filter(
                Q(user__profile__full_name__icontains=worker_name) | Q(user__username__icontains=worker_name)
            )

        return {
            "total_certificates": cert_qs.count(),
            "certificates": [
                {
                    "worker": getattr(getattr(c.user, 'profile', None), 'full_name', None) or c.user.username,
                    "certificate_type": c.certificate_type.name if c.certificate_type else "Sertifikat",
                    "created_at": str(c.created_at.date()) if c.created_at else "-"
                }
                for c in cert_qs[:10]
            ]
        }

    # 16. Kasblar va ularning standartlari
    def get_professions_and_standards(self, industry_name=None, **kwargs):
        """
        Tashkilotdagi barcha kasblar ro'yxati, ularning nizomlari va biriktirilgan tarmoq/sohalar.
        """
        from professions.models import Profession
        org_id = self._get_org_filter()
        qs = Profession.objects.all().select_related('industry', 'department')

        if not self.is_super_admin:
            if self.role == 'organization_leader':
                qs = qs.filter(Q(organization_id=org_id) | Q(department__leader_id=org_id))
            elif self.role == 'department_admin' and self.profile and self.profile.department_id:
                qs = qs.filter(department_id=self.profile.department_id)

        if industry_name:
            qs = qs.filter(industry__name__icontains=industry_name)

        return {
            "total_professions": qs.count(),
            "professions": [
                {
                    "id": pr.id,
                    "name": pr.name,
                    "industry": pr.industry.name if pr.industry else "-",
                    "has_nizom_file": bool(pr.nizom_file)
                }
                for pr in qs[:15]
            ]
        }

    # 17. Bo'lim ichki xabarlari va topshiriqlari
    def get_section_messages_and_tasks(self, **kwargs):
        """
        Bo'lim ichidagi rasmiy xabarlar, ogohlantirishlar va topshiriqlar ro'yxati.
        """
        from companies.models import SectionMessage
        qs = SectionMessage.objects.all().select_related('section', 'sender')

        if not self.is_super_admin:
            if self.role == 'organization_leader':
                org_id = self._get_org_filter()
                qs = qs.filter(section__department__leader_id=org_id)
            elif self.role == 'department_admin' and self.profile and self.profile.department_id:
                qs = qs.filter(section__department_id=self.profile.department_id)
            elif self.profile and self.profile.section_id:
                qs = qs.filter(section_id=self.profile.section_id)
            else:
                qs = qs.filter(sender=self.user)

        messages = []
        for m in qs[:10]:
            messages.append({
                "title": m.title,
                "section": m.section.name if m.section else "-",
                "sender": m.sender.get_full_name() or m.sender.username if m.sender else "-",
                "date": str(m.created_at.date()) if m.created_at else "-"
            })

        return {
            "total_messages": qs.count(),
            "messages": messages
        }


# Gemini Tool Declarations (17 ta to'liq vosita)
GEMINI_TOOLS_DECLARATION = [
    {
        "name": "search_safety_documents",
        "description": "RAG orqali mehnat muhofazasi qonunlari, yong'in, elektr, birinchi yordam, IHV va xavfsizlik me'yoriy hujjatlaridan qidirish.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "Qidirilayotgan xavfsizlik qoidasi, qonun yoki me'yoriy talab matni (masalan: yong'in paytida harakat, jgut qo'yish qoidalari, dielektrik qo'lqop)."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_user_profile_and_permissions",
        "description": "Foydalanuvchining o'z roli, vakolatlari, tashkilot nomi, lavozimi, bo'limi va xavfsizlik holatini qaytaradi.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "get_organization_and_structure_info",
        "description": "Tashkilot tuzilmasi, mavjud boshqarmalar, bo'limlar, rahbarlar va mas'ullar ro'yxati.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "get_workers_summary",
        "description": "Xodimlar ro'yxati, soni, qaysi bo'limdaligi, lavozimlari, bloklanganlar va malaka holati bo'yicha ma'lumot.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Xodim ismi, familiyasi yoki lavozimi bo'yicha qidiruv filtri."},
                "department_name": {"type": "STRING", "description": "Boshqarma nomi."},
                "section_name": {"type": "STRING", "description": "Bo'lim nomi."}
            }
        }
    },
    {
        "name": "get_violations_and_compliance",
        "description": "Mehnat muhofazasi qoidabuzarliklari, ogohlantirishlar, sabablari va jarimalar holati.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "worker_name": {"type": "STRING", "description": "Muayyan xodim ismi yoki familiyasi."},
                "only_active": {"type": "BOOLEAN", "description": "Faqat faol va jazolangan holatlarni ko'rsatish."}
            }
        }
    },
    {
        "name": "get_explanation_letters",
        "description": "Qoidabuzarlik sodir etgan xodimlarning tushuntirish xatlari va blokdan chiqarish holati.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "worker_name": {"type": "STRING", "description": "Xodim ismi yoki familiyasi."}
            }
        }
    },
    {
        "name": "get_ppe_safety_equipment_info",
        "description": "Shaxsiy himoya vositalari (IHV / PPE), berilgan vositalar, muddatlari va qabul holati.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "status": {"type": "STRING", "description": "Holat filtri: 'pending' (kutilmoqda) yoki 'accepted' (qabul qilingan)."}
            }
        }
    },
    {
        "name": "get_ppe_types_catalog",
        "description": "Tizimdagi barcha Shaxsiy himoya vositalari (IHV) turlari katalogi va standartlari.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "get_guidelines_status",
        "description": "Mehnat muhofazasi yo'riqnomalari: kirish, ichki, majburiy va kasbiy yo'riqnomalar va ularning qabul holati.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "guideline_type": {"type": "STRING", "description": "Yo'riqnoma turi: all, entry, mandatory yoki internal."}
            }
        }
    },
    {
        "name": "get_mandatory_guidelines_details",
        "description": "Majburiy yo'riqnomalar: tibbiy yordam, yong'in xavfsizligi va elektr xavfsizligi yo'riqnomalari.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "guideline_type": {"type": "STRING", "description": "Turi: 'medical', 'fire', 'electric'."}
            }
        }
    },
    {
        "name": "get_practices_and_assessments",
        "description": "Ish amaliyotlari (stajirovka), mas'ullar, amaliyot muddatlari va yakunlanganlik holati.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "get_practice_test_results",
        "description": "Stajirovka va amaliyotlar bo'yicha topshirilgan test sinovlari natijalari va ballar.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "worker_name": {"type": "STRING", "description": "Xodim ismi."}
            }
        }
    },
    {
        "name": "get_department_assessments",
        "description": "Boshqarma imtihonlari va bilim baholash testlari holati.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "is_active": {"type": "BOOLEAN", "description": "Faqat faol testlar."}
            }
        }
    },
    {
        "name": "get_medical_and_certificates_info",
        "description": "Xodimlarning tibbiy ko'rikdan o'tganlik holati va muddati o'tgan tibbiy ma'lumotlar.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "worker_name": {"type": "STRING", "description": "Xodim ismi."}
            }
        }
    },
    {
        "name": "get_employee_certificates",
        "description": "Xodimlarning kasbiy sertifikatlari va toifalari ro'yxati.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "worker_name": {"type": "STRING", "description": "Xodim ismi."}
            }
        }
    },
    {
        "name": "get_professions_and_standards",
        "description": "Tashkilotdagi mavjud kasblar, ularning nizomlari va tegishli sohalari.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "industry_name": {"type": "STRING", "description": "Soha nomi bo'yicha filtr."}
            }
        }
    },
    {
        "name": "get_section_messages_and_tasks",
        "description": "Bo'lim ichidagi xabarlar, rasmiy e'lonlar va topshiriqlar ro'yxati.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    }
]
