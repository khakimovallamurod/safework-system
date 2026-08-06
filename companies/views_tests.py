import random
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.utils import timezone

from accounts.mixins import SectionAdminRequiredMixin, AuthenticatedRequiredMixin, SectionMemberRequiredMixin
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

class TestListView(SectionAdminRequiredMixin, View):
    template_name = 'companies/tests/list.html'

    def get(self, request, *args, **kwargs):
        section = request.user.profile.section
        if not section:
            messages.error(request, "Siz hech qaysi bo'limga biriktirilmagansiz.")
            return redirect('dashboard')

        tests = list(WorkPracticeTest.objects.filter(section=section).prefetch_related('practice_permissions'))
        practices = list(SectionWorkPractice.objects.filter(section=section).order_by('-start_time'))

        # Attach assigned practice id set directly to each test object
        for test in tests:
            test.assigned_practice_ids = set(test.practice_permissions.values_list('practice_id', flat=True))

        context = self.get_role_context()
        context.update({
            'tests': tests,
            'practices': practices,
            'section': section,
        })
        return render(request, self.template_name, context)


class TestToggleStatusView(SectionAdminRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        section = request.user.profile.section
        test = get_object_or_404(WorkPracticeTest, pk=pk, section=section)
        test.is_active = not test.is_active
        test.save(update_fields=['is_active'])
        return JsonResponse({'is_active': test.is_active})


class TestPracticePermissionsView(SectionAdminRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        section = request.user.profile.section
        test = get_object_or_404(WorkPracticeTest, pk=pk, section=section)
        selected_ids = set(map(int, request.POST.getlist('practice_ids')))

        # Remove permissions that are no longer selected
        test.practice_permissions.exclude(practice_id__in=selected_ids).delete()

        # Add newly selected permissions
        existing_ids = set(test.practice_permissions.values_list('practice_id', flat=True))
        for pid in selected_ids - existing_ids:
            practice = get_object_or_404(SectionWorkPractice, pk=pid, section=section)
            WorkPracticeTestPermission.objects.create(test=test, practice=practice)

        messages.success(request, f"'{test.name}' uchun amaliyot ruxsatlari yangilandi.")
        return redirect('companies:test_list')


class TestCreateView(SectionAdminRequiredMixin, View):
    template_name = 'companies/tests/create.html'
    
    def get(self, request, *args, **kwargs):
        form = WorkPracticeTestForm()
        context = self.get_role_context()
        context.update({'form': form, 'title': 'Yangi test yaratish'})
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        form = WorkPracticeTestForm(request.POST)
        if form.is_valid():
            test = form.save(commit=False)
            section = request.user.profile.section
            test.section = section
            
            # Check if there are enough questions in the test base
            department = section.department
            test_base_questions = list(DepartmentTestBaseQuestion.objects.filter(department=department))
            
            if len(test_base_questions) < test.questions_count:
                messages.error(
                    request, 
                    f"Boshqarma test bazasida yetarli savol yo'q. Bazada {len(test_base_questions)} ta savol mavjud, lekin siz {test.questions_count} ta kiritdingiz."
                )
                context = self.get_role_context()
                context.update({'form': form, 'title': 'Yangi test yaratish'})
                return render(request, self.template_name, context)

            test.save()
            
            # Auto-populate questions
            random.shuffle(test_base_questions)
            selected_questions = test_base_questions[:test.questions_count]
            questions_to_create = [
                WorkPracticeTestQuestion(
                    test=test,
                    text=q.text,
                    option_1=q.option_1,
                    option_2=q.option_2,
                    option_3=q.option_3,
                    correct_option=q.correct_option
                )
                for q in selected_questions
            ]
            WorkPracticeTestQuestion.objects.bulk_create(questions_to_create)

            messages.success(request, f"Test muvaffaqiyatli yaratildi va bazadan {test.questions_count} ta savol olindi.")
            return redirect('companies:test_list')
        
        context = self.get_role_context()
        context.update({'form': form, 'title': 'Yangi test yaratish'})
        messages.error(request, "Test yaratishda xatolik yuz berdi.")
        return render(request, self.template_name, context)


class TestEditView(SectionAdminRequiredMixin, View):
    template_name = 'companies/tests/create.html'

    def get(self, request, pk, *args, **kwargs):
        section = request.user.profile.section
        test = get_object_or_404(WorkPracticeTest, pk=pk, section=section)
        form = WorkPracticeTestForm(instance=test)
        context = self.get_role_context()
        context.update({'form': form, 'test': test, 'title': 'Testni tahrirlash'})
        return render(request, self.template_name, context)

    def post(self, request, pk, *args, **kwargs):
        section = request.user.profile.section
        test = get_object_or_404(WorkPracticeTest, pk=pk, section=section)
        form = WorkPracticeTestForm(request.POST, instance=test)
        if form.is_valid():
            form.save()
            messages.success(request, "Test tahrirlandi.")
            return redirect('companies:test_list')
        
        context = self.get_role_context()
        context.update({'form': form, 'test': test, 'title': 'Testni tahrirlash'})
        messages.error(request, "Tahrirlashda xatolik bor.")
        return render(request, self.template_name, context)


class TestDeleteView(SectionAdminRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        section = request.user.profile.section
        test = get_object_or_404(WorkPracticeTest, pk=pk, section=section)
        test.delete()
        messages.success(request, "Test o'chirildi.")
        return redirect('companies:test_list')


class TestDetailView(SectionAdminRequiredMixin, View):
    template_name = 'companies/tests/detail.html'

    def get(self, request, pk, *args, **kwargs):
        section = request.user.profile.section
        test = get_object_or_404(WorkPracticeTest, pk=pk, section=section)
        questions = test.questions.all()
        context = self.get_role_context()
        context.update({
            'test': test,
            'questions': questions,
        })
        return render(request, self.template_name, context)


class QuestionCreateView(SectionAdminRequiredMixin, View):
    template_name = 'companies/tests/question_form.html'

    def get(self, request, test_pk, *args, **kwargs):
        section = request.user.profile.section
        test = get_object_or_404(WorkPracticeTest, pk=test_pk, section=section)
        form = WorkPracticeTestQuestionForm()
        context = self.get_role_context()
        context.update({'form': form, 'test': test})
        return render(request, self.template_name, context)

    def post(self, request, test_pk, *args, **kwargs):
        section = request.user.profile.section
        test = get_object_or_404(WorkPracticeTest, pk=test_pk, section=section)
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
        section = request.user.profile.section
        test = get_object_or_404(WorkPracticeTest, pk=test_pk, section=section)
        question = get_object_or_404(WorkPracticeTestQuestion, pk=pk, test=test)
        question.delete()
        messages.success(request, "Savol o'chirildi.")
        return redirect('companies:test_detail', pk=test.id)


class QuizStartView(SectionMemberRequiredMixin, View):
    template_name = 'companies/tests/quiz_start.html'

    def get(self, request, practice_pk, test_pk, *args, **kwargs):
        practice = get_object_or_404(SectionWorkPractice, pk=practice_pk)
        test = get_object_or_404(WorkPracticeTest, pk=test_pk, section=practice.section, is_active=True)
        
        # Verify user is assigned to this practice
        if not SectionWorkPracticeAssignee.objects.filter(practice=practice, user=request.user).exists():
            messages.error(request, "Siz ushbu amaliyotga biriktirilmagansiz.")
            return redirect('dashboard')
            
        # Allow test on the last day or after practice ends (date-level check)
        if practice.end_time.date() > timezone.now().date():
            messages.error(request, "Test faqat amaliyotning oxirgi kuni yoki undan keyin topshirilishi mumkin.")
            return redirect('work-practices')

        # Check attempts
        attempts_count = WorkPracticeTestAttempt.objects.filter(practice=practice, user=request.user, test=test).count()
        if attempts_count >= test.attempts_allowed:
            messages.error(request, "Urinishlar soni tugagan.")
            return redirect('dashboard')

        context = self.get_role_context()
        context.update({
            'practice': practice,
            'test': test,
            'attempts_count': attempts_count,
            'attempts_left': test.attempts_allowed - attempts_count
        })
        return render(request, self.template_name, context)
        
    def post(self, request, practice_pk, test_pk, *args, **kwargs):
        practice = get_object_or_404(SectionWorkPractice, pk=practice_pk)
        test = get_object_or_404(WorkPracticeTest, pk=test_pk, section=practice.section, is_active=True)
        
        attempts_count = WorkPracticeTestAttempt.objects.filter(practice=practice, user=request.user, test=test).count()
        if attempts_count >= test.attempts_allowed:
            messages.error(request, "Urinishlar soni tugagan.")
            return redirect('dashboard')
            
        # Create attempt
        attempt = WorkPracticeTestAttempt.objects.create(
            practice=practice,
            user=request.user,
            test=test
        )
        
        # Generate random questions
        all_questions = list(test.questions.all())
        random.shuffle(all_questions)
        selected_questions = all_questions[:test.questions_count]
        
        # Store selected question IDs in session
        request.session[f'quiz_attempt_{attempt.id}'] = [q.id for q in selected_questions]
        
        return redirect('companies:quiz_take', attempt_pk=attempt.id)


class QuizTakeView(SectionMemberRequiredMixin, View):
    template_name = 'companies/tests/quiz_take.html'

    def get(self, request, attempt_pk, *args, **kwargs):
        attempt = get_object_or_404(WorkPracticeTestAttempt, pk=attempt_pk, user=request.user)
        if attempt.finished_at:
            return redirect('companies:quiz_result', attempt_pk=attempt.id)
            
        question_ids = request.session.get(f'quiz_attempt_{attempt.id}', [])
        if not question_ids:
            messages.error(request, "Savollar topilmadi yoki sessiya tugagan.")
            return redirect('dashboard')
            
        questions = WorkPracticeTestQuestion.objects.filter(id__in=question_ids)
        # Order them dynamically as per the session list
        questions = sorted(questions, key=lambda q: question_ids.index(q.id))

        context = self.get_role_context()
        context.update({
            'attempt': attempt,
            'test': attempt.test,
            'questions': questions,
        })
        return render(request, self.template_name, context)

    def post(self, request, attempt_pk, *args, **kwargs):
        attempt = get_object_or_404(WorkPracticeTestAttempt, pk=attempt_pk, user=request.user)
        if attempt.finished_at:
            return redirect('companies:quiz_result', attempt_pk=attempt.id)
            
        question_ids = request.session.get(f'quiz_attempt_{attempt.id}', [])
        questions = WorkPracticeTestQuestion.objects.filter(id__in=question_ids)
        
        score = 0
        answers_to_create = []
        for question in questions:
            user_answer = request.POST.get(f'question_{question.id}')
            if user_answer and str(user_answer).isdigit():
                selected = int(user_answer)
                is_correct = (selected == question.correct_option)
                if is_correct:
                    score += 1
                answers_to_create.append(WorkPracticeTestAttemptAnswer(
                    attempt=attempt,
                    question=question,
                    selected_option=selected,
                    is_correct=is_correct,
                ))

        # Calculate percentage
        if len(question_ids) > 0:
            final_score = int((score / len(question_ids)) * 100)
        else:
            final_score = 0

        attempt.score = final_score
        attempt.finished_at = timezone.now()
        attempt.save()

        # Save per-question answers
        WorkPracticeTestAttemptAnswer.objects.bulk_create(answers_to_create, ignore_conflicts=True)

        # Mark worker as practice-qualified if score >= 60%
        if final_score >= 60:
            profile = request.user.profile
            if not profile.practice_qualified:
                profile.practice_qualified = True
                profile.save(update_fields=['practice_qualified_status', 'practice_qualified_at'])

        # Cleanup session
        if f'quiz_attempt_{attempt.id}' in request.session:
            del request.session[f'quiz_attempt_{attempt.id}']

        messages.success(request, f"Test yakunlandi. Natijangiz: {final_score}%")
        return redirect('companies:quiz_result', attempt_pk=attempt.id)


class QuizResultView(SectionMemberRequiredMixin, View):
    template_name = 'companies/tests/quiz_result.html'

    def get(self, request, attempt_pk, *args, **kwargs):
        attempt = get_object_or_404(WorkPracticeTestAttempt, pk=attempt_pk, user=request.user)
        answers = (
            attempt.answers
            .select_related('question')
            .order_by('id')
        )
        context = self.get_role_context()
        context.update({
            'attempt': attempt,
            'test': attempt.test,
            'answers': answers,
            'total': answers.count(),
            'correct_count': answers.filter(is_correct=True).count(),
        })
        return render(request, self.template_name, context)
