import csv
import io
import random
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import models as db_models
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from accounts.forms import get_department_admin_department, get_section_admin_section
from accounts.models import UserActivitySummary
from accounts.mixins import DepartmentAdminRequiredMixin, AuthenticatedRequiredMixin
from companies.models import (
    Department,
    Section,
    SectionMembership,
    DepartmentTestBaseQuestion,
    DepartmentAssessment,
    DepartmentAssessmentQuestion,
    DepartmentAssessmentNotification,
    DepartmentAssessmentAttempt,
    DepartmentAssessmentAttemptAnswer,
    SectionWorkPracticeAssignee,
    WorkPracticeTestAttempt,
)

User = get_user_model()


# ─── helpers ────────────────────────────────────────────────────────────────

def _dept_for_admin(user):
    return get_department_admin_department(user)


def _departments_for_assessment_user(user, role):
    profile = getattr(user, 'profile', None)
    if role.get('is_super_admin'):
        return Department.objects.all()
    if role.get('is_org_leader') and profile:
        return Department.objects.filter(leader=profile)
    dept = get_department_admin_department(user)
    if dept:
        return Department.objects.filter(pk=dept.pk)
    section = get_section_admin_section(user)
    if section:
        return Department.objects.filter(pk=section.department_id)
    return Department.objects.none()


def _assessment_scope_department(request, role):
    departments = _departments_for_assessment_user(request.user, role)
    selected_id = request.GET.get('department') or request.GET.get('dept')
    if selected_id and str(selected_id).isdigit():
        selected = departments.filter(pk=int(selected_id)).first()
        if selected:
            return selected, departments
    return departments.first(), departments


def _sections_for_assessment_scope(department, user, role):
    if role.get('is_section_admin'):
        section = get_section_admin_section(user)
        if section and section.department_id == department.id:
            return department.sections.filter(pk=section.pk)
        return Section.objects.none()
    return department.sections.all()


def _promotion_recommendations(users):
    rows = []
    for user in users:
        assessment_best = DepartmentAssessmentAttempt.objects.filter(
            user=user,
            finished_at__isnull=False,
            score__isnull=False,
        ).order_by('-score').first()
        practice_attempts = WorkPracticeTestAttempt.objects.filter(
            user=user,
            finished_at__isnull=False,
            score__isnull=False,
        )
        practice_best = practice_attempts.order_by('-score').first()
        accepted_practices = SectionWorkPracticeAssignee.objects.filter(
            user=user,
            accepted_by_responsible=True,
        ).count()
        activity = UserActivitySummary.objects.filter(user=user).first()
        assessment_score = assessment_best.score if assessment_best else 0
        practice_score = practice_best.score if practice_best else 0
        task_score = min(accepted_practices * 10, 20)
        activity_score = 10 if activity and (activity.requests_count >= 3 or activity.total_active_seconds >= 300) else 0
        score = int((assessment_score * 0.55) + (practice_score * 0.25) + task_score + activity_score)
        if assessment_score >= 85 and practice_score >= 70 and score >= 80:
            level = "Mansab/oylik oshirishga nomzod"
            badge = "bg-emerald-100 text-emerald-700"
        elif assessment_score >= 60:
            level = "Barqaror, kuzatuvda"
            badge = "bg-sky-100 text-sky-700"
        else:
            level = "Qayta o‘qitish kerak"
            badge = "bg-rose-100 text-rose-700"
        rows.append({
            'user': user,
            'assessment_score': assessment_score,
            'practice_score': practice_score,
            'accepted_practices': accepted_practices,
            'management_score': min(score, 100),
            'level': level,
            'badge': badge,
        })
    rows.sort(key=lambda item: -item['management_score'])
    return rows[:20]


def _all_dept_users(department):
    """Returns all section admins and workers in the department."""
    users = set()
    for section in department.sections.all():
        if section.supervisor_id:
            users.add(section.supervisor_id)
        for m in section.memberships.select_related('user'):
            users.add(m.user_id)
    return list(users)


def _user_dept(user):
    """Returns the Department for a section_admin or worker."""
    profile = getattr(user, 'profile', None)
    if not profile:
        return None
    if profile.section:
        return profile.section.department
    return None


# ─── Department Test Base views ──────────────────────────────────────────────

class DepartmentTestBaseListView(DepartmentAdminRequiredMixin, View):
    template_name = 'companies/assessment/test_base_list.html'

    def get(self, request):
        dept = _dept_for_admin(request.user)
        if not dept:
            messages.error(request, "Boshqarma topilmadi.")
            return redirect('dashboard')
        
        q = request.GET.get('q', '').strip()
        questions = DepartmentTestBaseQuestion.objects.filter(department=dept)
        if q:
            questions = questions.filter(text__icontains=q)
            
        ctx = self.get_role_context()
        ctx.update({'questions': questions, 'dept': dept, 'q': q})
        return render(request, self.template_name, ctx)


class DepartmentTestBaseCreateView(DepartmentAdminRequiredMixin, View):
    template_name = 'companies/assessment/test_base_form.html'

    def get(self, request):
        ctx = self.get_role_context()
        ctx.update({'title': "Yangi savol qo'shish"})
        return render(request, self.template_name, ctx)

    def post(self, request):
        dept = _dept_for_admin(request.user)
        if not dept:
            return redirect('dashboard')
            
        text = request.POST.get('text', '').strip()
        option_1 = request.POST.get('option_1', '').strip()
        option_2 = request.POST.get('option_2', '').strip()
        option_3 = request.POST.get('option_3', '').strip()
        try:
            correct_option = int(request.POST.get('correct_option', 0))
        except ValueError:
            correct_option = 0

        if not all([text, option_1, option_2, option_3]) or correct_option not in [1, 2, 3]:
            messages.error(request, "Barcha maydonlar to'ldirilishi va to'g'ri variant tanlanishi kerak.")
            ctx = self.get_role_context()
            ctx.update({'title': "Yangi savol qo'shish"})
            return render(request, self.template_name, ctx)

        DepartmentTestBaseQuestion.objects.create(
            department=dept, text=text,
            option_1=option_1, option_2=option_2, option_3=option_3,
            correct_option=correct_option,
        )
        
        if 'save_and_add' in request.POST:
            messages.success(request, "Savol qo'shildi. Yangi savol qo'shing.")
            return redirect('test-base-create')
            
        messages.success(request, "Savol muvaffaqiyatli qo'shildi.")
        return redirect('test-base-list')


class DepartmentTestBaseEditView(DepartmentAdminRequiredMixin, View):
    template_name = 'companies/assessment/test_base_form.html'

    def get(self, request, pk):
        dept = _dept_for_admin(request.user)
        question = get_object_or_404(DepartmentTestBaseQuestion, pk=pk, department=dept)
        ctx = self.get_role_context()
        ctx.update({'title': "Savolni tahrirlash", 'question': question})
        return render(request, self.template_name, ctx)

    def post(self, request, pk):
        dept = _dept_for_admin(request.user)
        question = get_object_or_404(DepartmentTestBaseQuestion, pk=pk, department=dept)
        
        text = request.POST.get('text', '').strip()
        option_1 = request.POST.get('option_1', '').strip()
        option_2 = request.POST.get('option_2', '').strip()
        option_3 = request.POST.get('option_3', '').strip()
        try:
            correct_option = int(request.POST.get('correct_option', 0))
        except ValueError:
            correct_option = 0

        if not all([text, option_1, option_2, option_3]) or correct_option not in [1, 2, 3]:
            messages.error(request, "Barcha maydonlar to'ldirilishi va to'g'ri variant tanlanishi kerak.")
            ctx = self.get_role_context()
            ctx.update({'title': "Savolni tahrirlash", 'question': question})
            return render(request, self.template_name, ctx)

        question.text = text
        question.option_1 = option_1
        question.option_2 = option_2
        question.option_3 = option_3
        question.correct_option = correct_option
        question.save()
            
        messages.success(request, "Savol tahrirlandi.")
        return redirect('test-base-list')


class DepartmentTestBaseDeleteView(DepartmentAdminRequiredMixin, View):
    def post(self, request, pk):
        dept = _dept_for_admin(request.user)
        question = get_object_or_404(DepartmentTestBaseQuestion, pk=pk, department=dept)
        question.delete()
        messages.success(request, "Savol o'chirildi.")
        return redirect('test-base-list')


class DepartmentTestBaseImportView(DepartmentAdminRequiredMixin, View):
    def post(self, request):
        dept = _dept_for_admin(request.user)
        if not dept:
            messages.error(request, "Boshqarma topilmadi.")
            return redirect('dashboard')

        csv_file = request.FILES.get('csv_file')
        if not csv_file:
            messages.error(request, "Iltimos, fayl yuklang.")
            return redirect('test-base-list')

        if not csv_file.name.endswith('.csv'):
            messages.error(request, "Faqat .csv formatidagi fayllarni yuklash mumkin.")
            return redirect('test-base-list')

        try:
            # Decode the file contents
            decoded_file = csv_file.read().decode('utf-8')
            io_string = io.StringIO(decoded_file)
            reader = csv.reader(io_string, delimiter=',')
            
            # Skip the header
            next(reader, None)

            questions_to_create = []
            skipped = 0
            
            for row in reader:
                if len(row) < 5:
                    skipped += 1
                    continue
                    
                text = row[0].strip()
                option_1 = row[1].strip()
                option_2 = row[2].strip()
                option_3 = row[3].strip()
                correct_str = row[4].strip().upper()
                
                # Map correct option
                if correct_str == 'A':
                    correct_option = 1
                elif correct_str == 'B':
                    correct_option = 2
                elif correct_str == 'C':
                    correct_option = 3
                else:
                    skipped += 1
                    continue
                    
                if not all([text, option_1, option_2, option_3]):
                    skipped += 1
                    continue

                questions_to_create.append(
                    DepartmentTestBaseQuestion(
                        department=dept,
                        text=text,
                        option_1=option_1,
                        option_2=option_2,
                        option_3=option_3,
                        correct_option=correct_option
                    )
                )

            if questions_to_create:
                DepartmentTestBaseQuestion.objects.bulk_create(questions_to_create)
                messages.success(
                    request, 
                    f"Muvaffaqiyatli {len(questions_to_create)} ta savol yuklandi." 
                    + (f" ({skipped} ta qator o'tkazib yuborildi)" if skipped else "")
                )
            else:
                messages.warning(request, "Fayldan hech qanday to'g'ri savol topilmadi yoki barcha qatorlar xato.")

        except Exception as e:
            messages.error(request, f"Faylni o'qishda xatolik yuz berdi: {str(e)}")

        return redirect('test-base-list')


# ─── Department Admin views ──────────────────────────────────────────────────

class AssessmentListView(DepartmentAdminRequiredMixin, View):
    template_name = 'companies/assessment/list.html'

    def test_func(self):
        role = self.get_role_context()
        return (
            role.get('is_super_admin')
            or role.get('is_org_leader')
            or role.get('is_department_admin')
            or role.get('is_section_admin')
        )

    def get(self, request):
        dept = _dept_for_admin(request.user)
        if not dept:
            role = self.get_role_context()
            if role.get('is_super_admin') or role.get('is_org_leader') or role.get('is_section_admin'):
                return redirect('assessment-overview')
            messages.error(request, "Boshqarma topilmadi.")
            return redirect('dashboard')
        assessments = DepartmentAssessment.objects.filter(department=dept).annotate(
            q_count=db_models.Count('questions'),
            attempt_count=db_models.Count('attempts'),
            notif_count=db_models.Count('notifications'),
        )
        ctx = self.get_role_context()
        ctx.update({'assessments': assessments, 'dept': dept})
        return render(request, self.template_name, ctx)


class AssessmentCreateView(DepartmentAdminRequiredMixin, View):
    template_name = 'companies/assessment/create.html'

    def get(self, request):
        ctx = self.get_role_context()
        ctx.update({'title': "Yangi test yaratish"})
        return render(request, self.template_name, ctx)

    def post(self, request):
        dept = _dept_for_admin(request.user)
        if not dept:
            return redirect('dashboard')
        name = request.POST.get('name', '').strip()
        try:
            duration = int(request.POST.get('duration', 0))
            questions_count = int(request.POST.get('questions_count', 0))
            attempts_allowed = int(request.POST.get('attempts_allowed', 1))
        except ValueError:
            messages.error(request, "Raqamli maydonlar to'g'ri to'ldirilmagan.")
            return redirect('assessment-create')
        notes = request.POST.get('notes', '').strip()

        if not name or duration < 1 or questions_count < 1 or attempts_allowed < 1:
            messages.error(request, "Barcha maydonlar to'ldirilishi shart.")
            ctx = self.get_role_context()
            ctx.update({'title': "Yangi test yaratish"})
            return render(request, self.template_name, ctx)

        # Check if enough questions exist in the test base
        test_base_questions = list(DepartmentTestBaseQuestion.objects.filter(department=dept))
        if len(test_base_questions) < questions_count:
            messages.error(
                request,
                f"Test bazasida yetarli savol yo'q. Bazada {len(test_base_questions)} ta savol mavjud, lekin siz {questions_count} ta kiritdingiz."
            )
            ctx = self.get_role_context()
            ctx.update({'title': "Yangi test yaratish"})
            return render(request, self.template_name, ctx)

        assessment = DepartmentAssessment.objects.create(
            department=dept, name=name, duration=duration,
            questions_count=questions_count, attempts_allowed=attempts_allowed,
            notes=notes, created_by=request.user,
        )

        # Auto-populate questions
        random.shuffle(test_base_questions)
        selected_questions = test_base_questions[:questions_count]
        questions_to_create = [
            DepartmentAssessmentQuestion(
                assessment=assessment,
                text=q.text,
                option_1=q.option_1,
                option_2=q.option_2,
                option_3=q.option_3,
                correct_option=q.correct_option
            )
            for q in selected_questions
        ]
        DepartmentAssessmentQuestion.objects.bulk_create(questions_to_create)

        messages.success(request, f"'{name}' testi yaratildi va test bazasidan {questions_count} ta savol olindi.")
        return redirect('assessment-detail', pk=assessment.pk)


class AssessmentDetailView(DepartmentAdminRequiredMixin, View):
    template_name = 'companies/assessment/detail.html'

    def get(self, request, pk):
        dept = _dept_for_admin(request.user)
        assessment = get_object_or_404(DepartmentAssessment, pk=pk, department=dept)
        questions = assessment.questions.all()
        sections = dept.sections.all()
        ctx = self.get_role_context()
        ctx.update({'assessment': assessment, 'questions': questions, 'sections': sections})
        return render(request, self.template_name, ctx)


class AssessmentToggleActiveView(DepartmentAdminRequiredMixin, View):
    def post(self, request, pk):
        dept = _dept_for_admin(request.user)
        assessment = get_object_or_404(DepartmentAssessment, pk=pk, department=dept)
        assessment.is_active = not assessment.is_active
        assessment.save(update_fields=['is_active'])
        return JsonResponse({'is_active': assessment.is_active})


class AssessmentPublishView(DepartmentAdminRequiredMixin, View):
    def post(self, request, pk):
        dept = _dept_for_admin(request.user)
        assessment = get_object_or_404(DepartmentAssessment, pk=pk, department=dept)

        if assessment.is_published:
            messages.warning(request, "Test allaqachon joriy qilingan.")
            return redirect('assessment-detail', pk=pk)

        if assessment.questions.count() < assessment.questions_count:
            messages.error(
                request,
                f"Kamida {assessment.questions_count} ta savol qo'shilishi kerak "
                f"(hozir {assessment.questions.count()} ta)."
            )
            return redirect('assessment-detail', pk=pk)

        section_ids = request.POST.getlist('sections')
        if not section_ids:
            messages.error(request, "Iltimos, kamida bitta bo'limni tanlang.")
            return redirect('assessment-detail', pk=pk)

        # Mark published
        assessment.is_published = True
        assessment.is_active = True
        assessment.published_at = timezone.now()
        assessment.save(update_fields=['is_published', 'is_active', 'published_at'])

        # Send notifications only to selected sections
        user_ids = set()
        
        # Check if 'all' is selected
        if 'all' in section_ids:
            user_ids = set(_all_dept_users(dept))
        else:
            # Gather users for selected sections
            selected_sections = Section.objects.filter(id__in=section_ids, department=dept)
            for section in selected_sections:
                if section.supervisor_id:
                    user_ids.add(section.supervisor_id)
                for m in section.memberships.select_related('user'):
                    user_ids.add(m.user_id)
        
        user_ids = list(user_ids)

        existing = set(
            DepartmentAssessmentNotification.objects.filter(
                assessment=assessment
            ).values_list('user_id', flat=True)
        )
        new_notifs = [
            DepartmentAssessmentNotification(assessment=assessment, user_id=uid)
            for uid in user_ids if uid not in existing
        ]
        DepartmentAssessmentNotification.objects.bulk_create(new_notifs, ignore_conflicts=True)

        messages.success(
            request,
            f"Test joriy qilindi. {len(new_notifs)} ta foydalanuvchiga xabarnoma yuborildi."
        )
        return redirect('assessment-detail', pk=pk)


class AssessmentOverviewView(DepartmentAdminRequiredMixin, View):
    """Barcha published testlar uchun umumiy hisobot."""
    template_name = 'companies/assessment/overview.html'

    def test_func(self):
        role = self.get_role_context()
        return (
            role.get('is_super_admin')
            or role.get('is_org_leader')
            or role.get('is_department_admin')
            or role.get('is_section_admin')
        )

    def get(self, request):
        role = self.get_role_context()
        dept, departments = _assessment_scope_department(request, role)
        if not dept:
            return redirect('dashboard')
        status = request.GET.get('status', 'all')
        published = DepartmentAssessment.objects.filter(
            department=dept, is_published=True
        ).annotate(
            attempt_count=db_models.Count('attempts', filter=db_models.Q(attempts__finished_at__isnull=False)),
            passed_count=db_models.Count('attempts', filter=db_models.Q(
                attempts__finished_at__isnull=False, attempts__score__gte=60
            )),
            notif_count=db_models.Count('notifications'),
            confirmed_count=db_models.Count('notifications', filter=db_models.Q(notifications__is_confirmed=True)),
        ).order_by('-published_at')

        # Sections with failed workers
        sections = _sections_for_assessment_scope(dept, request.user, role).prefetch_related('memberships__user__profile')
        failed_workers = []
        passed_workers = []
        pending_workers = []
        all_workers = []
        for section in sections:
            for m in section.memberships.select_related('user__profile').all():
                all_workers.append(m.user)
                profile = getattr(m.user, 'profile', None)
                if profile and profile.assessment_qualified is False:
                    failed_workers.append({'user': m.user, 'section': section})
                elif profile and profile.assessment_qualified is True:
                    passed_workers.append({'user': m.user, 'section': section})
                else:
                    pending_workers.append({'user': m.user, 'section': section})

        # Sort sections by failed count
        section_stats = []
        for section in sections:
            members = list(section.memberships.select_related('user__profile'))
            fail = sum(1 for m in members
                       if getattr(getattr(m.user, 'profile', None), 'assessment_qualified', None) is False)
            section_stats.append({'section': section, 'total': len(members), 'failed': fail})
        section_stats.sort(key=lambda x: -x['failed'])

        visible_workers = {
            'passed': passed_workers,
            'failed': failed_workers,
            'pending': pending_workers,
        }.get(status, passed_workers + failed_workers + pending_workers)
        top_attempts = (
            DepartmentAssessmentAttempt.objects
            .filter(
                assessment__department=dept,
                user_id__in=[user.id for user in all_workers],
                finished_at__isnull=False,
                score__isnull=False,
            )
            .select_related('user__profile', 'assessment')
            .order_by('-score', '-finished_at')[:10]
        )
        recommendations = _promotion_recommendations(all_workers)
        ctx = role
        ctx.update({
            'dept': dept,
            'departments': departments,
            'selected_status': status,
            'published': published,
            'failed_workers': failed_workers,
            'passed_workers': passed_workers,
            'pending_workers': pending_workers,
            'visible_workers': visible_workers,
            'passed_total': len(passed_workers),
            'pending_total': len(pending_workers),
            'section_stats': section_stats,
            'failed_total': len(failed_workers),
            'worker_total': len(all_workers),
            'top_attempts': top_attempts,
            'recommendations': recommendations,
        })
        return render(request, self.template_name, ctx)


class AssessmentEditView(DepartmentAdminRequiredMixin, View):
    template_name = 'companies/assessment/create.html'

    def get(self, request, pk):
        role = self.get_role_context()
        dept, departments = _assessment_scope_department(request, role)
        assessment = get_object_or_404(
            DepartmentAssessment,
            pk=pk,
            department__in=departments,
        )
        dept = assessment.department
        status = request.GET.get('status', 'all')
        if assessment.is_published:
            messages.warning(request, "Joriy qilingan testni tahrirlash mumkin emas.")
            return redirect('assessment-detail', pk=pk)
        ctx = self.get_role_context()
        ctx.update({'title': "Testni tahrirlash", 'assessment': assessment})
        return render(request, self.template_name, ctx)

    def post(self, request, pk):
        dept = _dept_for_admin(request.user)
        assessment = get_object_or_404(DepartmentAssessment, pk=pk, department=dept)
        if assessment.is_published:
            return redirect('assessment-detail', pk=pk)
        name = request.POST.get('name', '').strip()
        try:
            duration = int(request.POST.get('duration', 0))
            questions_count = int(request.POST.get('questions_count', 0))
            attempts_allowed = int(request.POST.get('attempts_allowed', 1))
        except ValueError:
            messages.error(request, "Raqamli maydonlar to'g'ri to'ldirilmagan.")
            return redirect('assessment-edit', pk=pk)
        notes = request.POST.get('notes', '').strip()
        if not name or duration < 1 or questions_count < 1 or attempts_allowed < 1:
            messages.error(request, "Barcha maydonlar to'ldirilishi shart.")
            ctx = self.get_role_context()
            ctx.update({'title': "Testni tahrirlash", 'assessment': assessment})
            return render(request, self.template_name, ctx)
        assessment.name = name
        assessment.duration = duration
        assessment.questions_count = questions_count
        assessment.attempts_allowed = attempts_allowed
        assessment.notes = notes
        assessment.save()
        messages.success(request, "Test yangilandi.")
        return redirect('assessment-detail', pk=pk)


class AssessmentDeleteView(DepartmentAdminRequiredMixin, View):
    def post(self, request, pk):
        dept = _dept_for_admin(request.user)
        assessment = get_object_or_404(DepartmentAssessment, pk=pk, department=dept)
        if assessment.is_published:
            messages.warning(request, "Joriy qilingan testni o'chirib bo'lmaydi.")
            return redirect('assessment-list')
        assessment.delete()
        messages.success(request, "Test o'chirildi.")
        return redirect('assessment-list')


class AssessmentQuestionAddView(DepartmentAdminRequiredMixin, View):
    template_name = 'companies/assessment/question_form.html'

    def get(self, request, pk):
        dept = _dept_for_admin(request.user)
        assessment = get_object_or_404(DepartmentAssessment, pk=pk, department=dept)
        if assessment.is_published:
            messages.warning(request, "Joriy qilingan testga savol qo'shib bo'lmaydi.")
            return redirect('assessment-detail', pk=pk)
        ctx = self.get_role_context()
        ctx.update({'assessment': assessment})
        return render(request, self.template_name, ctx)

    def post(self, request, pk):
        dept = _dept_for_admin(request.user)
        assessment = get_object_or_404(DepartmentAssessment, pk=pk, department=dept)
        if assessment.is_published:
            return redirect('assessment-detail', pk=pk)

        text = request.POST.get('text', '').strip()
        option_1 = request.POST.get('option_1', '').strip()
        option_2 = request.POST.get('option_2', '').strip()
        option_3 = request.POST.get('option_3', '').strip()
        try:
            correct_option = int(request.POST.get('correct_option', 0))
        except ValueError:
            correct_option = 0

        if not all([text, option_1, option_2, option_3]) or correct_option not in [1, 2, 3]:
            messages.error(request, "Barcha maydonlar to'ldirilishi va to'g'ri variant tanlanishi kerak.")
            ctx = self.get_role_context()
            ctx.update({'assessment': assessment})
            return render(request, self.template_name, ctx)

        DepartmentAssessmentQuestion.objects.create(
            assessment=assessment, text=text,
            option_1=option_1, option_2=option_2, option_3=option_3,
            correct_option=correct_option,
        )

        if 'save_and_add' in request.POST:
            messages.success(request, "Savol qo'shildi. Yangi savol qo'shing.")
            return redirect('assessment-question-add', pk=pk)

        messages.success(request, "Savol qo'shildi.")
        return redirect('assessment-detail', pk=pk)


class AssessmentQuestionDeleteView(DepartmentAdminRequiredMixin, View):
    def post(self, request, pk, qpk):
        dept = _dept_for_admin(request.user)
        assessment = get_object_or_404(DepartmentAssessment, pk=pk, department=dept)
        if not assessment.is_published:
            question = get_object_or_404(DepartmentAssessmentQuestion, pk=qpk, assessment=assessment)
            question.delete()
            messages.success(request, "Savol o'chirildi.")
        return redirect('assessment-detail', pk=pk)


class AssessmentReportView(DepartmentAdminRequiredMixin, View):
    template_name = 'companies/assessment/report.html'

    def test_func(self):
        role = self.get_role_context()
        return (
            role.get('is_super_admin')
            or role.get('is_org_leader')
            or role.get('is_department_admin')
            or role.get('is_section_admin')
        )

    def get(self, request, pk):
        role = self.get_role_context()
        dept = _dept_for_admin(request.user)
        assessment = get_object_or_404(DepartmentAssessment, pk=pk, department=dept)
        status = request.GET.get('status', 'all')

        # All sections in dept
        sections = _sections_for_assessment_scope(dept, request.user, role).prefetch_related('memberships__user__profile')

        section_data = []
        for section in sections:
            members = list(section.memberships.select_related('user__profile').all())
            if section.supervisor:
                supervisor_ids = [section.supervisor_id]
            else:
                supervisor_ids = []

            worker_rows = []
            for m in members:
                u = m.user
                notif = DepartmentAssessmentNotification.objects.filter(
                    assessment=assessment, user=u
                ).first()
                best_attempt = DepartmentAssessmentAttempt.objects.filter(
                    assessment=assessment, user=u, finished_at__isnull=False
                ).order_by('-score').first()
                worker_rows.append({
                    'user': u,
                    'notif': notif,
                    'confirmed': notif.is_confirmed if notif else False,
                    'best_score': best_attempt.score if best_attempt else None,
                    'passed': best_attempt.score >= 60 if best_attempt and best_attempt.score is not None else None,
                    'attempt': best_attempt,
                })

            if status == 'passed':
                worker_rows = [r for r in worker_rows if r['passed'] is True]
            elif status == 'failed':
                worker_rows = [r for r in worker_rows if r['passed'] is False]
            elif status == 'pending':
                worker_rows = [r for r in worker_rows if r['passed'] is None]

            # Sort: passed first, then by score desc
            worker_rows.sort(key=lambda x: (
                0 if x['passed'] is True else (1 if x['passed'] is False else 2),
                -(x['best_score'] or -1),
            ))

            passed_count = sum(1 for r in worker_rows if r['passed'] is True)
            failed_count = sum(1 for r in worker_rows if r['passed'] is False)
            section_data.append({
                'section': section,
                'rows': worker_rows,
                'total': len(worker_rows),
                'passed': passed_count,
                'failed': failed_count,
                'has_failed': failed_count > 0,
            })

        # Global stats
        total_notifs = DepartmentAssessmentNotification.objects.filter(assessment=assessment).count()
        confirmed = DepartmentAssessmentNotification.objects.filter(
            assessment=assessment, is_confirmed=True
        ).count()
        all_attempts = DepartmentAssessmentAttempt.objects.filter(
            assessment=assessment, finished_at__isnull=False
        )
        passed_all = all_attempts.filter(score__gte=60).count()
        failed_all = all_attempts.filter(score__lt=60).count()

        top_rows = []
        for data in section_data:
            top_rows.extend([row for row in data['rows'] if row['best_score'] is not None])
        top_rows.sort(key=lambda row: -(row['best_score'] or 0))
        ctx = role
        ctx.update({
            'assessment': assessment,
            'selected_status': status,
            'section_data': section_data,
            'total_notifs': total_notifs,
            'confirmed': confirmed,
            'passed_all': passed_all,
            'failed_all': failed_all,
            'top_rows': top_rows[:10],
        })
        return render(request, self.template_name, ctx)


# ─── Section admin / Worker views ───────────────────────────────────────────

class AssessmentInboxView(AuthenticatedRequiredMixin, View):
    template_name = 'companies/assessment/inbox.html'

    def get(self, request):
        notifs = DepartmentAssessmentNotification.objects.filter(
            user=request.user,
            assessment__is_published=True,
            assessment__is_active=True,
        ).select_related('assessment').order_by('-created_at')

        inbox_items = []
        for notif in notifs:
            a = notif.assessment
            attempts = DepartmentAssessmentAttempt.objects.filter(
                assessment=a, user=request.user
            ).order_by('-started_at')
            best = attempts.filter(finished_at__isnull=False).order_by('-score').first()
            attempts_used = attempts.count()
            inbox_items.append({
                'notif': notif,
                'assessment': a,
                'best_score': best.score if best else None,
                'best_attempt_id': best.id if best else None,
                'attempts_used': attempts_used,
                'attempts_left': max(0, a.attempts_allowed - attempts_used),
                'can_take': attempts_used < a.attempts_allowed,
            })

        ctx = self.get_role_context()
        ctx.update({'inbox_items': inbox_items})
        return render(request, self.template_name, ctx)


class AssessmentNotificationConfirmView(AuthenticatedRequiredMixin, View):
    def post(self, request, npk):
        notif = get_object_or_404(
            DepartmentAssessmentNotification, pk=npk, user=request.user
        )
        if not notif.is_confirmed:
            notif.is_confirmed = True
            notif.confirmed_at = timezone.now()
            notif.save(update_fields=['is_confirmed', 'confirmed_at'])
            messages.success(request, f"'{notif.assessment.name}' testi qabul qilindi.")
        # Redirect back to referring page (inbox) or assessment-inbox
        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER', '')
        if next_url and next_url != request.build_absolute_uri():
            return redirect(next_url)
        return redirect('assessment-inbox')


class AssessmentTakeView(AuthenticatedRequiredMixin, View):
    template_name = 'companies/assessment/take.html'

    def get(self, request, pk):
        assessment = get_object_or_404(
            DepartmentAssessment, pk=pk, is_published=True, is_active=True
        )
        notif = DepartmentAssessmentNotification.objects.filter(
            assessment=assessment, user=request.user
        ).first()
        if not notif:
            messages.error(request, "Sizga bu test uchun ruxsat berilmagan.")
            return redirect('assessment-inbox')

        attempts_used = DepartmentAssessmentAttempt.objects.filter(
            assessment=assessment, user=request.user
        ).count()
        if attempts_used >= assessment.attempts_allowed:
            messages.warning(request, "Urinishlar soni tugagan.")
            return redirect('assessment-inbox')

        # Create attempt
        attempt = DepartmentAssessmentAttempt.objects.create(
            assessment=assessment, user=request.user
        )
        # Pick random questions
        all_q = list(assessment.questions.all())
        random.shuffle(all_q)
        selected = all_q[:assessment.questions_count]
        request.session[f'dept_assessment_{attempt.id}'] = [q.id for q in selected]

        questions = selected
        ctx = self.get_role_context()
        ctx.update({
            'assessment': assessment,
            'attempt': attempt,
            'questions': questions,
            'duration_seconds': assessment.duration * 60,
        })
        return render(request, self.template_name, ctx)

    def post(self, request, pk):
        assessment = get_object_or_404(DepartmentAssessment, pk=pk)
        attempt_id = request.POST.get('attempt_id')
        attempt = get_object_or_404(
            DepartmentAssessmentAttempt, pk=attempt_id, user=request.user
        )
        if attempt.finished_at:
            return redirect('assessment-result', apk=attempt.id)

        question_ids = request.session.get(f'dept_assessment_{attempt.id}', [])
        questions = DepartmentAssessmentQuestion.objects.filter(id__in=question_ids)

        score = 0
        answers_to_create = []
        for q in questions:
            ans = request.POST.get(f'question_{q.id}')
            if ans and str(ans).isdigit():
                selected = int(ans)
                correct = (selected == q.correct_option)
                if correct:
                    score += 1
                answers_to_create.append(DepartmentAssessmentAttemptAnswer(
                    attempt=attempt, question=q,
                    selected_option=selected, is_correct=correct,
                ))

        total = len(question_ids) or 1
        final_score = int((score / total) * 100)

        attempt.score = final_score
        attempt.finished_at = timezone.now()
        attempt.save()

        DepartmentAssessmentAttemptAnswer.objects.bulk_create(
            answers_to_create, ignore_conflicts=True
        )

        # Update worker qualification status
        profile = request.user.profile
        if final_score >= 60:
            profile.assessment_qualified = True
        else:
            profile.assessment_qualified = False
        profile.save(update_fields=['assessment_qualified'])

        # Cleanup session
        request.session.pop(f'dept_assessment_{attempt.id}', None)

        messages.success(request, f"Test yakunlandi. Natijangiz: {final_score}%")
        return redirect('assessment-result', apk=attempt.id)


class AssessmentResultView(AuthenticatedRequiredMixin, View):
    template_name = 'companies/assessment/result.html'

    def get(self, request, apk):
        attempt = get_object_or_404(
            DepartmentAssessmentAttempt, pk=apk, user=request.user
        )
        answers = attempt.dept_answers.select_related('question').order_by('id')
        ctx = self.get_role_context()
        ctx.update({
            'attempt': attempt,
            'assessment': attempt.assessment,
            'answers': answers,
            'total': answers.count(),
            'correct_count': answers.filter(is_correct=True).count(),
        })
        return render(request, self.template_name, ctx)
