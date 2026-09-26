import random
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.utils import timezone
from django.db import transaction
from django.db.models import Q

from accounts.mixins import SectionAdminRequiredMixin, AuthenticatedRequiredMixin
from accounts.notifications import send_action_notification
from companies.forms import WorkPracticeTestForm, WorkPracticeTestQuestionForm
from companies.models import (
    Section,
    WorkPracticeTest,
    WorkPracticeTestQuestion,
    WorkPracticeTestAttempt,
    WorkPracticeTestAttemptAnswer,
    WorkPracticeTestPermission,
    SectionWorkPractice,
    SectionWorkPracticeAssignee,
    DepartmentTestBaseQuestion
)

def _get_sections_for_test_management(request):
    if request.user.is_superuser:
        return Section.objects.select_related('department').all()

    profile = getattr(request.user, 'profile', None)
    if not profile:
        return Section.objects.none()

    if profile.role in ['org_leader', 'organization_leader']:
        from accounts.views import _org_leader_departments
        depts = _org_leader_departments(request.user)
        return Section.objects.filter(department__in=depts).select_related('department')

    if profile.role == 'department_admin':
        from companies.models import Department
        depts = Department.objects.filter(Q(supervisor=request.user) | Q(pk=profile.department_id if profile.department_id else None))
        return Section.objects.filter(department__in=depts).select_related('department')

    return Section.objects.filter(
        Q(id=profile.section_id) | Q(supervisor=request.user) | Q(memberships__user=request.user)
    ).select_related('department').distinct()


class TestListView(SectionAdminRequiredMixin, View):
    template_name = 'companies/tests/list.html'

    def get(self, request, *args, **kwargs):
        sections = _get_sections_for_test_management(request)
        if not sections.exists():
            messages.error(request, "Sizga biriktirilgan bo'limlar topilmadi.")
            return redirect('dashboard')

        selected_section_id = request.GET.get('section', '').strip()
        if selected_section_id.isdigit():
            filtered_sections = sections.filter(id=int(selected_section_id))
            active_sections = filtered_sections if filtered_sections.exists() else sections
        else:
            active_sections = sections

        tests = list(WorkPracticeTest.objects.filter(section__in=active_sections).select_related('section').prefetch_related('practice_permissions'))
        practices = list(SectionWorkPractice.objects.filter(section__in=active_sections).select_related('section').order_by('-start_time'))

        # Attach assigned practice id set directly to each test object
        for test in tests:
            test.assigned_practice_ids = set(test.practice_permissions.values_list('practice_id', flat=True))

        context = self.get_role_context()
        context.update({
            'tests': tests,
            'practices': practices,
            'section': sections.first() if sections.count() == 1 else None,
            'sections': sections,
            'selected_section_id': int(selected_section_id) if selected_section_id.isdigit() else None,
        })
        return render(request, self.template_name, context)


class TestToggleStatusView(SectionAdminRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        sections = _get_sections_for_test_management(request)
        test = get_object_or_404(WorkPracticeTest, pk=pk, section__in=sections)
        test.is_active = not test.is_active
        test.save(update_fields=['is_active'])
        return JsonResponse({'is_active': test.is_active})


class TestPracticePermissionsView(SectionAdminRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        sections = _get_sections_for_test_management(request)
        test = get_object_or_404(WorkPracticeTest, pk=pk, section__in=sections)
        selected_ids = {int(pid) for pid in request.POST.getlist('practice_ids') if str(pid).isdigit()}

        # Remove permissions that are no longer selected
        test.practice_permissions.exclude(practice_id__in=selected_ids).delete()

        # Add newly selected permissions
        existing_ids = set(test.practice_permissions.values_list('practice_id', flat=True))
        for pid in selected_ids - existing_ids:
            practice = get_object_or_404(SectionWorkPractice, pk=pid, section__in=sections)
            WorkPracticeTestPermission.objects.create(test=test, practice=practice)

        if selected_ids - existing_ids:
            try:
                creator_name = (request.user.profile.full_name if hasattr(request.user, 'profile') and request.user.profile and request.user.profile.full_name else request.user.username)
                send_action_notification(
                    title="Stajirovkaga test joriy qilindi",
                    message=f"{creator_name} tomonidan «{test.name}» testi ish amaliyotiga biriktirildi va joriy qilindi.",
                    notif_type='test',
                    url='/ish-amaliyotlari/',
                    section=test.section,
                    department=test.section.department if test.section else None,
                    exclude_users=[request.user]
                )
            except Exception:
                pass

        messages.success(request, f"'{test.name}' uchun amaliyot ruxsatlari yangilandi.")
        return redirect('companies:test_list')


class TestCreateView(SectionAdminRequiredMixin, View):
    template_name = 'companies/tests/create.html'
    
    def get(self, request, *args, **kwargs):
        sections = _get_sections_for_test_management(request)
        if not sections.exists():
            messages.error(request, "Sizga biriktirilgan bo'limlar topilmadi.")
            return redirect('dashboard')
        form = WorkPracticeTestForm()
        context = self.get_role_context()
        context.update({'form': form, 'title': 'Yangi test yaratish', 'sections': sections})
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        sections = _get_sections_for_test_management(request)
        if not sections.exists():
            messages.error(request, "Sizga biriktirilgan bo'limlar topilmadi.")
            return redirect('dashboard')

        section_id = request.POST.get('section_id')
        if section_id and str(section_id).isdigit():
            section = sections.filter(pk=int(section_id)).first()
        else:
            section = sections.first()

        if not section:
            messages.error(request, "Test uchun bo'lim tanlanmadi.")
            return redirect('companies:test_create')

        form = WorkPracticeTestForm(request.POST)
        if form.is_valid():
            test = form.save(commit=False)
            test.section = section

            if test.start_time and test.end_time and test.start_time >= test.end_time:
                messages.error(request, "Boshlanish vaqti tugash vaqtidan oldin bo'lishi kerak.")
                context = self.get_role_context()
                context.update({'form': form, 'title': 'Yangi test yaratish', 'sections': sections})
                return render(request, self.template_name, context)
            
            # Check if there are enough unique questions in the test base
            department = section.department
            raw_base_questions = list(DepartmentTestBaseQuestion.objects.filter(department=department))
            seen_texts = set()
            test_base_questions = []
            for q in raw_base_questions:
                t = q.text.strip().lower()
                if t not in seen_texts:
                    seen_texts.add(t)
                    test_base_questions.append(q)
            
            if len(test_base_questions) < test.questions_count:
                messages.error(
                    request, 
                    f"Boshqarma test bazasida yetarli noyob savol yo'q. Bazada {len(test_base_questions)} ta turli savol mavjud, lekin siz {test.questions_count} ta kiritdingiz."
                )
                context = self.get_role_context()
                context.update({'form': form, 'title': 'Yangi test yaratish', 'sections': sections})
                return render(request, self.template_name, context)

            test.save()
            
            # Populate questions from all unique base questions
            questions_to_create = [
                WorkPracticeTestQuestion(
                    test=test,
                    text=q.text,
                    option_1=q.option_1,
                    option_2=q.option_2,
                    option_3=q.option_3,
                    correct_option=q.correct_option
                )
                for q in test_base_questions
            ]
            WorkPracticeTestQuestion.objects.bulk_create(questions_to_create)

            creator_profile = getattr(request.user, 'profile', None)
            creator_name = (creator_profile.full_name if creator_profile and creator_profile.full_name else request.user.username)
            send_action_notification(
                title="Yangi test joriy qilindi",
                message=f"«{section.name}» bo‘limi ({creator_name}) o‘z ishchilariga test joriy qildi: «{test.name}» ({test.questions_count} ta savol, {test.duration} daqiqa).",
                notif_type='test',
                url=reverse('companies:test_detail', kwargs={'pk': test.id}),
                section=section,
                department=section.department
            )

            messages.success(request, f"Test yaratildi va bazadan {len(questions_to_create)} ta savol yuklandi. Har bir urinishda {test.questions_count} ta tasodifiy savol beriladi.")
            return redirect('companies:test_list')
        
        context = self.get_role_context()
        context.update({'form': form, 'title': 'Yangi test yaratish', 'sections': sections})
        messages.error(request, "Test yaratishda xatolik yuz berdi.")
        return render(request, self.template_name, context)


class TestEditView(SectionAdminRequiredMixin, View):
    template_name = 'companies/tests/create.html'

    def get(self, request, pk, *args, **kwargs):
        sections = _get_sections_for_test_management(request)
        test = get_object_or_404(WorkPracticeTest, pk=pk, section__in=sections)
        form = WorkPracticeTestForm(instance=test)
        context = self.get_role_context()
        context.update({'form': form, 'test': test, 'title': 'Testni tahrirlash', 'sections': sections})
        return render(request, self.template_name, context)

    def post(self, request, pk, *args, **kwargs):
        sections = _get_sections_for_test_management(request)
        test = get_object_or_404(WorkPracticeTest, pk=pk, section__in=sections)
        form = WorkPracticeTestForm(request.POST, instance=test)
        if form.is_valid():
            test_obj = form.save(commit=False)
            if test_obj.start_time and test_obj.end_time and test_obj.start_time >= test_obj.end_time:
                messages.error(request, "Boshlanish vaqti tugash vaqtidan oldin bo'lishi kerak.")
                context = self.get_role_context()
                context.update({'form': form, 'test': test, 'title': 'Testni tahrirlash', 'sections': sections})
                return render(request, self.template_name, context)
            test_obj.save()
            messages.success(request, "Test tahrirlandi.")
            return redirect('companies:test_list')
        
        context = self.get_role_context()
        context.update({'form': form, 'test': test, 'title': 'Testni tahrirlash', 'sections': sections})
        messages.error(request, "Tahrirlashda xatolik bor.")
        return render(request, self.template_name, context)


class TestStopView(SectionAdminRequiredMixin, View):
    """Bo'lim testini muddatidan oldin to'xtatish."""

    def post(self, request, pk, *args, **kwargs):
        sections = _get_sections_for_test_management(request)
        test = get_object_or_404(WorkPracticeTest, pk=pk, section__in=sections)
        stop_reason = (request.POST.get('stop_reason') or '').strip()
        if not stop_reason:
            messages.error(request, "Testni to‘xtatish uchun izoh (sabab) kiritish shart!")
            return redirect('companies:test_detail', pk=pk)

        test.is_active = False
        test.is_stopped = True
        test.stopped_at = timezone.now()
        test.stop_reason = stop_reason
        test.stopped_by = request.user
        test.save(update_fields=['is_active', 'is_stopped', 'stopped_at', 'stop_reason', 'stopped_by'])

        messages.success(request, f"Test to‘xtatildi. Sabab: {stop_reason}")
        return redirect('companies:test_detail', pk=pk)


class TestDeleteView(SectionAdminRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        sections = _get_sections_for_test_management(request)
        test = get_object_or_404(WorkPracticeTest, pk=pk, section__in=sections)
        test.delete()
        messages.success(request, "Test o'chirildi.")
        return redirect('companies:test_list')


class TestDetailView(SectionAdminRequiredMixin, View):
    template_name = 'companies/tests/detail.html'

    def get(self, request, pk, *args, **kwargs):
        sections = _get_sections_for_test_management(request)
        test = WorkPracticeTest.objects.filter(
            Q(section__in=sections) |
            Q(section__department__supervisor=request.user) |
            Q(section__department_id=getattr(request.user.profile, 'department_id', None)) |
            Q(practice_permissions__practice__responsible_user=request.user) |
            Q(practice_permissions__practice__section__in=sections)
        ).distinct().filter(pk=pk).first()

        if not test:
            if request.user.is_superuser:
                test = get_object_or_404(WorkPracticeTest, pk=pk)
            else:
                messages.error(request, "Test topilmadi yoki ko'rish huquqi yo'q.")
                return redirect('work-practices')

        questions = test.questions.all()
        attempts = WorkPracticeTestAttempt.objects.filter(
            test=test, finished_at__isnull=False
        ).select_related('user', 'user__profile', 'practice', 'test').order_by('-finished_at')
        context = self.get_role_context()
        context.update({
            'test': test,
            'questions': questions,
            'attempts': attempts,
        })
        return render(request, self.template_name, context)


class QuestionCreateView(SectionAdminRequiredMixin, View):
    template_name = 'companies/tests/question_form.html'

    def get(self, request, test_pk, *args, **kwargs):
        sections = _get_sections_for_test_management(request)
        test = get_object_or_404(WorkPracticeTest, pk=test_pk, section__in=sections)
        form = WorkPracticeTestQuestionForm()
        context = self.get_role_context()
        context.update({'form': form, 'test': test})
        return render(request, self.template_name, context)

    def post(self, request, test_pk, *args, **kwargs):
        sections = _get_sections_for_test_management(request)
        test = get_object_or_404(WorkPracticeTest, pk=test_pk, section__in=sections)
        form = WorkPracticeTestQuestionForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.test = test
            question.save()
            messages.success(request, "Savol muvaffaqiyatli qo'shildi.")
            return redirect('companies:test_detail', pk=test.id)
        
        context = self.get_role_context()
        context.update({'form': form, 'test': test})
        messages.error(request, "Savol qo'shishda xatolik.")
        return render(request, self.template_name, context)


class QuestionDeleteView(SectionAdminRequiredMixin, View):
    def post(self, request, test_pk, pk, *args, **kwargs):
        sections = _get_sections_for_test_management(request)
        test = get_object_or_404(WorkPracticeTest, pk=test_pk, section__in=sections)
        question = get_object_or_404(WorkPracticeTestQuestion, pk=pk, test=test)
        question.delete()
        messages.success(request, "Savol o'chirildi.")
        return redirect('companies:test_detail', pk=test.id)


def _is_test_linked_to_practice(test, practice):
    return (
        test.section_id == practice.section_id
        or (practice.section and test.section and test.section.department_id == practice.section.department_id)
        or test.practice_permissions.filter(practice=practice).exists()
    )


def _practice_window_error(practice, test):
    """Stajirovka/test vaqt oynasi yopiq bo'lsa, xabar matnini qaytaradi (aks holda None)."""
    now = timezone.now()
    if practice.start_time and practice.start_time > now:
        return f"Ushbu stajirovka testi hali boshlanmagan. Boshlanish vaqti: {timezone.localtime(practice.start_time):%d.%m.%Y %H:%M}"
    if practice.end_time and practice.end_time < now:
        return f"Ushbu stajirovka testi topshirish muddati tugagan (Tugash vaqti: {timezone.localtime(practice.end_time):%d.%m.%Y %H:%M})."
    if practice.closed_at:
        return "Ushbu stajirovka yakunlangan va yopilgan."
    if test.is_stopped:
        return "Test muddatidan oldin to‘xtatilgan."
    is_valid, msg = test.is_in_time_window
    if not is_valid:
        return msg
    return None


def _can_view_attempt(request, attempt):
    """Natijani ko'rish huquqi: amaliyotchining o'zi, mas'ul ustoz, yaratuvchi va tegishli rahbarlar."""
    user = request.user
    if attempt.user_id == user.id or user.is_superuser or user.is_staff:
        return True
    practice = attempt.practice
    if practice.responsible_user_id == user.id or practice.created_by_id == user.id:
        return True
    profile = getattr(user, 'profile', None)
    if not profile:
        return False
    if profile.role == 'super_admin':
        return True
    if profile.role in ['org_leader', 'organization_leader', 'department_admin', 'section_admin']:
        return _get_sections_for_test_management(request).filter(pk=practice.section_id).exists()
    return False


def _finalize_quiz_attempt(attempt, post_data=None):
    """
    Urinishni yakunlaydi va ballni hisoblaydi. Faqat bir marta ishlaydi (ikki marta yuborishdan himoya).
    post_data=None bo'lsa (vaqt tugagan), javoblar hisobga olinmaydi.
    Qaytaradi: (final_score, passed) yoki urinish allaqachon yakunlangan bo'lsa None.
    """
    question_ids = list(attempt.question_ids or [])
    questions = list(WorkPracticeTestQuestion.objects.filter(id__in=question_ids))
    total = len(questions)

    correct = 0
    answers_to_create = []
    if post_data is not None:
        for question in questions:
            user_answer = post_data.get(f'question_{question.id}')
            if user_answer and str(user_answer).isdigit() and int(user_answer) in (1, 2, 3):
                selected = int(user_answer)
                is_correct = (selected == question.correct_option)
                if is_correct:
                    correct += 1
                answers_to_create.append(WorkPracticeTestAttemptAnswer(
                    attempt=attempt,
                    question=question,
                    selected_option=selected,
                    is_correct=is_correct,
                ))

    # Butun sonli arifmetika: float xatoliklarsiz foizni pastga yaxlitlash
    final_score = (correct * 100) // total if total else 0
    now = timezone.now()

    with transaction.atomic():
        updated = WorkPracticeTestAttempt.objects.filter(
            pk=attempt.pk, finished_at__isnull=True
        ).update(score=final_score, finished_at=now)
        if not updated:
            return None
        WorkPracticeTestAttemptAnswer.objects.bulk_create(answers_to_create, ignore_conflicts=True)

    attempt.score = final_score
    attempt.finished_at = now
    passed = attempt.is_passed

    # Testdan o'tgan amaliyotchi mustaqil ishlashga ruxsat oladi
    if passed:
        profile = getattr(attempt.user, 'profile', None)
        if profile and not profile.practice_qualified:
            profile.practice_qualified = True
            profile.save(update_fields=['practice_qualified_status', 'practice_qualified_at'])

    return final_score, passed


def _close_expired_attempts(practice, user, test):
    """Vaqti tugab, yakunlanmay qolgan urinishlarni 0 ball bilan yopish."""
    grace = timezone.timedelta(seconds=WorkPracticeTestAttempt.SUBMIT_GRACE_SECONDS)
    open_attempts = WorkPracticeTestAttempt.objects.filter(
        practice=practice, user=user, test=test, finished_at__isnull=True
    ).select_related('test', 'user__profile')
    active = None
    for att in open_attempts:
        if timezone.now() > att.deadline + grace:
            _finalize_quiz_attempt(att, post_data=None)
        elif active is None:
            active = att
    return active


class QuizStartView(AuthenticatedRequiredMixin, View):
    template_name = 'companies/tests/quiz_start.html'

    def _load(self, request, practice_pk, test_pk):
        practice = get_object_or_404(
            SectionWorkPractice.objects.select_related('section', 'section__department', 'responsible_user__profile'),
            pk=practice_pk,
        )
        test = get_object_or_404(
            WorkPracticeTest.objects.select_related('section'), pk=test_pk, is_active=True
        )
        if not _is_test_linked_to_practice(test, practice):
            messages.error(request, "Ushbu test ushbu amaliyotga biriktirilmagan.")
            return None, None, redirect('work-practices')

        # Faqat amaliyotga biriktirilgan xodim test topshira oladi
        if not SectionWorkPracticeAssignee.objects.filter(practice=practice, user=request.user).exists():
            messages.error(request, "Siz ushbu amaliyotga biriktirilmagansiz.")
            return None, None, redirect('work-practices')

        window_error = _practice_window_error(practice, test)
        if window_error:
            messages.warning(request, window_error)
            return None, None, redirect('work-practices')
        return practice, test, None

    def get(self, request, practice_pk, test_pk, *args, **kwargs):
        practice, test, error_response = self._load(request, practice_pk, test_pk)
        if error_response:
            return error_response

        active_attempt = _close_expired_attempts(practice, request.user, test)
        if active_attempt:
            return redirect('companies:quiz_take', attempt_pk=active_attempt.id)

        attempts_count = WorkPracticeTestAttempt.objects.filter(practice=practice, user=request.user, test=test).count()
        if attempts_count >= test.attempts_allowed:
            messages.error(request, "Urinishlar soni tugagan.")
            return redirect('work-practices')

        context = self.get_role_context()
        context.update({
            'practice': practice,
            'test': test,
            'attempts_count': attempts_count,
            'attempts_left': test.attempts_allowed - attempts_count
        })
        return render(request, self.template_name, context)

    def post(self, request, practice_pk, test_pk, *args, **kwargs):
        practice, test, error_response = self._load(request, practice_pk, test_pk)
        if error_response:
            return error_response

        # Yakunlanmagan faol urinish bo'lsa, yangisini ochmasdan o'shanga qaytarish
        active_attempt = _close_expired_attempts(practice, request.user, test)
        if active_attempt:
            return redirect('companies:quiz_take', attempt_pk=active_attempt.id)

        # Sync any missing questions from department test base
        dept = practice.section.department if practice.section else None
        if dept:
            existing_texts = set(t.strip().lower() for t in test.questions.values_list('text', flat=True))
            dept_questions = DepartmentTestBaseQuestion.objects.filter(department=dept)
            missing_q = []
            for dq in dept_questions:
                key = dq.text.strip().lower()
                if key in existing_texts:
                    continue
                existing_texts.add(key)
                missing_q.append(WorkPracticeTestQuestion(
                    test=test,
                    text=dq.text,
                    option_1=dq.option_1,
                    option_2=dq.option_2,
                    option_3=dq.option_3,
                    correct_option=dq.correct_option
                ))
            if missing_q:
                WorkPracticeTestQuestion.objects.bulk_create(missing_q)

        # Generate random questions
        all_question_ids = list(test.questions.values_list('id', flat=True))
        if not all_question_ids:
            messages.error(request, "Ushbu testda savollar mavjud emas. Bo‘lim rahbariga murojaat qiling.")
            return redirect('work-practices')
        random.shuffle(all_question_ids)
        selected_ids = all_question_ids[:test.questions_count]

        with transaction.atomic():
            # Parallel so'rovlarda urinishlar sonidan oshib ketmaslik uchun qatorni qulflash
            SectionWorkPracticeAssignee.objects.select_for_update().filter(practice=practice, user=request.user).first()
            attempts_count = WorkPracticeTestAttempt.objects.filter(practice=practice, user=request.user, test=test).count()
            if attempts_count >= test.attempts_allowed:
                messages.error(request, "Urinishlar soni tugagan.")
                return redirect('work-practices')
            attempt = WorkPracticeTestAttempt.objects.create(
                practice=practice,
                user=request.user,
                test=test,
                question_ids=selected_ids,
            )

        return redirect('companies:quiz_take', attempt_pk=attempt.id)


class QuizTakeView(AuthenticatedRequiredMixin, View):
    template_name = 'companies/tests/quiz_take.html'

    def _get_attempt(self, request, attempt_pk):
        return get_object_or_404(
            WorkPracticeTestAttempt.objects.select_related(
                'test', 'practice', 'practice__section', 'practice__section__department', 'user', 'user__profile'
            ),
            pk=attempt_pk,
            user=request.user,
        )

    def _notify_result(self, request, attempt, final_score, passed):
        try:
            worker_name = (request.user.profile.full_name if hasattr(request.user, 'profile') and request.user.profile and request.user.profile.full_name else request.user.username)
            if not passed:
                notif_title = f"Ogohlantirish: Testdan o‘tmadi ({worker_name})"
                notif_msg = f"{worker_name} «{attempt.practice.name}» stajirovkasi doirasidagi «{attempt.test.name}» testidan o‘ta olmadi (Natija: {final_score}%, o‘tish bali: {attempt.test.pass_percentage}%)."
            else:
                notif_title = f"Stajirovka testi topshirildi ({worker_name})"
                notif_msg = f"{worker_name} «{attempt.practice.name}» stajirovkasi doirasidagi «{attempt.test.name}» testidan muvaffaqiyatli o‘tdi (Natija: {final_score}%)."

            target_users = [attempt.practice.responsible_user] if attempt.practice.responsible_user_id else None
            send_action_notification(
                title=notif_title,
                message=notif_msg,
                notif_type='test',
                url=reverse('companies:quiz_result', kwargs={'attempt_pk': attempt.id}),
                section=attempt.practice.section,
                department=attempt.practice.section.department if attempt.practice.section else None,
                target_users=target_users,
                exclude_users=[request.user]
            )
        except Exception:
            pass

    def get(self, request, attempt_pk, *args, **kwargs):
        attempt = self._get_attempt(request, attempt_pk)
        if attempt.finished_at:
            return redirect('companies:quiz_result', attempt_pk=attempt.id)

        # Server tomonidagi vaqt nazorati: vaqt tugagan bo'lsa urinish avtomatik yopiladi
        if attempt.remaining_seconds <= 0:
            result = _finalize_quiz_attempt(attempt, post_data=None)
            if result:
                self._notify_result(request, attempt, *result)
            messages.warning(request, "Test vaqti tugagan. Urinish yakunlandi.")
            return redirect('companies:quiz_result', attempt_pk=attempt.id)

        is_valid, msg = attempt.test.is_in_time_window
        if not is_valid:
            messages.warning(request, msg)
            return redirect('work-practices')

        question_ids = list(attempt.question_ids or [])
        if not question_ids:
            # Eski urinishlar uchun (savollar sessiyada saqlangan)
            question_ids = request.session.get(f'quiz_attempt_{attempt.id}', [])
            if question_ids:
                attempt.question_ids = question_ids
                attempt.save(update_fields=['question_ids'])
        if not question_ids:
            messages.error(request, "Savollar topilmadi yoki sessiya tugagan.")
            return redirect('work-practices')

        questions = list(WorkPracticeTestQuestion.objects.filter(id__in=question_ids))
        # Order them dynamically as per the stored list
        order = {qid: i for i, qid in enumerate(question_ids)}
        questions.sort(key=lambda q: order.get(q.id, 0))

        # Shuffle options for each question
        for q in questions:
            opts = [
                (1, q.option_1),
                (2, q.option_2),
                (3, q.option_3),
            ]
            random.shuffle(opts)
            q.shuffled_options = opts

        context = self.get_role_context()
        context.update({
            'attempt': attempt,
            'test': attempt.test,
            'questions': questions,
            'remaining_seconds': attempt.remaining_seconds,
        })
        return render(request, self.template_name, context)

    def post(self, request, attempt_pk, *args, **kwargs):
        attempt = self._get_attempt(request, attempt_pk)
        if attempt.finished_at:
            return redirect('companies:quiz_result', attempt_pk=attempt.id)

        if not attempt.question_ids:
            session_ids = request.session.get(f'quiz_attempt_{attempt.id}', [])
            if session_ids:
                attempt.question_ids = session_ids
                attempt.save(update_fields=['question_ids'])

        # Vaqt tugaganidan keyin (qo'shimcha muhlatdan so'ng) yuborilgan javoblar qabul qilinmaydi
        grace = timezone.timedelta(seconds=WorkPracticeTestAttempt.SUBMIT_GRACE_SECONDS)
        is_late = timezone.now() > attempt.deadline + grace
        result = _finalize_quiz_attempt(attempt, post_data=None if is_late else request.POST)
        if result is None:
            # Ikki marta yuborilgan (allaqachon yakunlangan)
            return redirect('companies:quiz_result', attempt_pk=attempt.id)
        final_score, passed = result

        # Cleanup session
        request.session.pop(f'quiz_attempt_{attempt.id}', None)

        self._notify_result(request, attempt, final_score, passed)

        if is_late:
            messages.warning(request, "Test vaqti tugaganidan keyin yuborildi, javoblar qabul qilinmadi.")
        else:
            messages.success(request, f"Test yakunlandi. Natijangiz: {final_score}%")
        return redirect('companies:quiz_result', attempt_pk=attempt.id)


class QuizResultView(AuthenticatedRequiredMixin, View):
    template_name = 'companies/tests/quiz_result.html'

    def get(self, request, attempt_pk, *args, **kwargs):
        attempt = get_object_or_404(
            WorkPracticeTestAttempt.objects.select_related(
                'test', 'practice', 'practice__section', 'practice__responsible_user__profile', 'user', 'user__profile'
            ),
            pk=attempt_pk,
        )
        if not _can_view_attempt(request, attempt):
            messages.error(request, "Natijani ko‘rish huquqi yo‘q.")
            return redirect('work-practices')
        if not attempt.finished_at:
            if attempt.user_id == request.user.id:
                return redirect('companies:quiz_take', attempt_pk=attempt.id)
            messages.info(request, "Test hali yakunlanmagan.")
            return redirect('work-practices')

        answers = list(
            attempt.answers
            .select_related('question')
            .order_by('id')
        )
        total = len(attempt.question_ids) if attempt.question_ids else len(answers)
        correct_count = sum(1 for a in answers if a.is_correct)
        context = self.get_role_context()
        context.update({
            'attempt': attempt,
            'test': attempt.test,
            'answers': answers,
            'total': total,
            'correct_count': correct_count,
            'wrong_count': max(total - correct_count, 0),
            'is_owner': attempt.user_id == request.user.id,
        })
        return render(request, self.template_name, context)


class PracticeCompletionCertificateView(AuthenticatedRequiredMixin, View):
    """Mustaqil ishlashga ruxsatnoma (stajirovka yakuni hujjati) - faqat testdan o'tganda."""
    template_name = 'companies/tests/practice_certificate.html'

    def get(self, request, attempt_pk, *args, **kwargs):
        attempt = get_object_or_404(
            WorkPracticeTestAttempt.objects.select_related(
                'test',
                'practice',
                'practice__section',
                'practice__section__department',
                'practice__section__supervisor__profile',
                'practice__responsible_user__profile',
                'user',
                'user__profile',
            ),
            pk=attempt_pk,
        )
        if not _can_view_attempt(request, attempt):
            messages.error(request, "Hujjatni ko‘rish huquqi yo‘q.")
            return redirect('work-practices')
        if not attempt.is_passed:
            messages.error(request, "Ruxsatnoma faqat testdan muvaffaqiyatli o‘tilganda beriladi.")
            return redirect('work-practices')

        assignment = SectionWorkPracticeAssignee.objects.filter(
            practice=attempt.practice, user=attempt.user
        ).first()
        context = self.get_role_context()
        context.update({
            'attempt': attempt,
            'test': attempt.test,
            'practice': attempt.practice,
            'trainee': attempt.user,
            'trainee_profile': getattr(attempt.user, 'profile', None),
            'assignment': assignment,
            'issued_at': attempt.finished_at,
        })
        return render(request, self.template_name, context)
