from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from .models import Section, Subject
from c_activities.models import Activity, ActivitySubmission
from b_enrollment.models import UserProfile, StudentSubject
from django.urls import reverse
import json
from django.http import JsonResponse, HttpResponseRedirect, HttpRequest, HttpResponse, FileResponse
from .forms import CreateSubjectForm
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth import update_session_auth_hash
from django.core.paginator import Paginator
from django.core.mail import send_mail, get_connection
from django.utils import timezone
from django.db.models import Max
from django.utils.timezone import localtime
from django.core import serializers
from django.db.models import Avg
from django.db.models import Max, Subquery, OuterRef
import os
# Create your views here.
def select_user_related(user):
    try:
        return UserProfile.objects.select_related('user').get(user=user)
    except UserProfile.DoesNotExist:
        return None

def select_subject_by_id(subject_id):
    return Subject.objects.filter(subject_id=subject_id).first()

def select_activity_by_id(activity_id):
    return Activity.objects.filter(activity_id=activity_id).first()

def get_all_activities_in_subject(subject_id):
    subject = Subject.objects.filter(subject_id=subject_id).first()
    if not subject:
        return None
    return subject.activities.all().order_by('-created_at')

def get_student_submission_by_id(student, activity):
    return ActivitySubmission.objects.filter(student=student, activity=activity).first()

def get_submission_by_id(submission_id):
    return ActivitySubmission.objects.filter(id=submission_id).first()

def test(request):
    return render(request, 'a_classroom/test.html')

def index(request):
    if not hasattr(request.user, 'userprofile'):
        messages.error(request, "Your account is incomplete. Please contact the administrator.")
        return redirect('register:login')

    if request.user.is_staff or request.user.userprofile.role == "Dean":
        if request.headers.get("HX-Request") == "true":
            return render(request, 'a_classroom/sidebar/sidebar.html')
        return render(request, 'a_classroom/a.admin/admin.html')

    if request.user.userprofile.role == "Instructor":
        subjects = Subject.objects.filter(instructor=request.user).order_by('-subject_id')
        if request.headers.get("HX-Request") == "true":
            return render(request, 'a_classroom/sidebar/sidebar.html', {"subjects": subjects})

        return render(request, 'a_classroom/b.instructor/instructor.html', {"subjects" : subjects})

    elif request.user.userprofile.role == "Student":
        subjects = list(request.user.joined_subjects.all())
        if request.headers.get("HX-Request") == "true":
            return render(request, 'a_classroom/sidebar/sidebar.html', {"subjects" : subjects})

        return render(request, 'a_classroom/c.student/student.html', {"subjects" : subjects})


    return render(request, 'a_classroom/index.html')

@method_decorator(never_cache, name='dispatch')
class CreateSubjectView(View):
    def get(self, request):
        form = CreateSubjectForm()
        sections = Section.objects.all()
        return render(request, 'a_classroom/subject/create_subject.html', {"form": form, "sections" : sections})

    def post(self, request):
        action_type = request.POST.get("action")

        if action_type == "create_subject":
            if request.headers.get("HX-Request"):
                if not request.POST.get("processing"):
                    return render(request, "a_classroom/subject/partials/progress_bar.html")
                else:
                    return self.process_subject_creation(request)

            return self.process_subject_creation(request)
            
        form = CreateSubjectForm()
        return render(request, 'a_classroom/create_subject.html', {"form": form})

    def process_subject_creation(self, request):
        form = CreateSubjectForm(request.POST)
        if form.is_valid():
            course_code = form.cleaned_data["course_code"]
            section_name = form.cleaned_data["section_name"]
            name = form.cleaned_data["name"]

            section, created = Section.objects.get_or_create(name=section_name)

            subject = Subject.objects.filter(
                instructor=request.user, 
                course_code=course_code,
                section=section, 
                name=name).first()

            if subject:
                messages.error(request, f"{course_code} for section {section_name} already exists.")
                return redirect("a_classroom:index")
            else:
                subject = Subject.objects.create(
                    instructor=request.user,
                    course_code=course_code,
                    section=section,
                    name=name
                )
                messages.success(request, f"{course_code} for section {section_name} has been created.")
                response = reverse("a_classroom:v", args=[subject.subject_id])
                return redirect(response)
            
            form = CreateSubjectForm() 

            response = HttpResponse()
            response["HX-Redirect"] = reverse("a_classroom:v", args=[subject.subject_id])
            return response

        return render(request, 'a_classroom/create_subject.html', {"form": form})

def user_settings(request):
    user_profile = select_user_related(request.user)
    if not user_profile:
        return redirect("a_classoom:index")
    email = request.user.email
    return render(request, 'a_classroom/settings/setting.html', {"user_profile" : user_profile, "email" : email})


@never_cache
def view_subject(request, subject_id):
    subject = select_subject_by_id(subject_id)
    activities = get_all_activities_in_subject(subject_id)
    if activities is None:
        return redirect("a_classroom:index")

    students = subject.students.all()
    instructor = subject.instructor
    trigger = request.headers.get("HX-Trigger")
    if request.headers.get("HX-Request") == "true":
        if trigger == "subject":
            return render(request, 'a_classroom/subject/partials/subject.html', {
                "subject" : subject,
                "activities" : activities,
            })
        elif trigger == "students":
            return render(request, 'a_classroom/subject/partials/people.html', {
                "subject" : subject,
                "instructor" : instructor,
                "students" : students
            })
    return render(request, 'a_classroom/subject/subject_view.html', {"subject" : subject, "activities" : activities})

class EditAccountView(View):
    def get(self, request):
        trigger = request.headers.get("HX-Trigger")
        if request.headers.get("HX-Request") == "true":
            if trigger == "edit-account":
                user = get_object_or_404(User, id = request.user.id)
                return render(request, 'a_classroom/settings/partials/edit.account.html', {"user" : user})

        return redirect("a_classroom:index")

    def post(self, request):
        user = get_object_or_404(User, id=request.user.id)

        first_name = request.POST.get('first_name', '').strip().title()
        last_name = request.POST.get('last_name', '').strip().title()
        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()

        if password or confirm_password:
            if not password or not confirm_password:
                messages.error(request, 'Both password fields must be filled to change your password.')
                return redirect('a_classroom:setting')
            elif password != confirm_password:
                messages.error(request, 'Passwords do not match.')
                return redirect('a_classroom:setting')
            else:
                user.set_password(password)
                update_session_auth_hash(request, user)

        user.first_name = first_name
        user.last_name = last_name
        user.save()

        messages.success(request, 'Your profile has been updated successfully!')
        return redirect('a_classroom:setting')

class ActivityView(View):
    def get(self, request, activity_id):
        subject_id = request.GET.get('subject_id')
        user_profile = select_user_related(request.user)
        subject = select_subject_by_id(subject_id)
        if not subject:
            return redirect("a_classroom:index")

        activity = get_object_or_404(Activity, subject=subject, activity_id=activity_id)

        if user_profile.role == "Instructor":
            highest_score_subquery = ActivitySubmission.objects.filter(
                activity=activity,
                student=OuterRef('student')
            ).order_by('-score').values('score')[:1]
            
            highest_submissions = ActivitySubmission.objects.filter(
                activity=activity,
                student__in=activity.submissions.values('student').distinct(),
                score=Subquery(highest_score_subquery)
            ).select_related("student").order_by('student__username', '-submitted_at')
            
            unique_highest_submissions = []
            seen_students = set()
            for submission in highest_submissions:
                if submission.student.id not in seen_students:
                    unique_highest_submissions.append(submission)
                    seen_students.add(submission.student.id)
            
            if activity.type == "activity":
                unique_highest_submissions = [
                    sub for sub in unique_highest_submissions 
                    if sub.status in ["submitted", "returned", "In Progress"]
                ]
            
            index = int(request.GET.get('index', 0))
            
            current_submission = None
            if unique_highest_submissions and 0 <= index < len(unique_highest_submissions):
                current_submission = unique_highest_submissions[index]
            
            return render(request, 'c_activities/activity.partial/student.submission.html', {
                "activity": activity,
                "user_profile": user_profile,
                "activity_submissions": unique_highest_submissions,
                "current_submission": current_submission,
                "index": index,
                "total_submissions": len(unique_highest_submissions),
                "subject_id": subject_id,
            })

        elif user_profile.role == "Student":
            action_type = request.GET.get("action")
            submissions = activity.submissions.filter(student=request.user).order_by("-submitted_at")
            submission = submissions.filter(status__in=["submitted", "returned"]).first()
            if not submission:
                submission = submissions.first()

            return_quiz_submission = submissions.filter(status="returned", student=request.user).first()

            submission_count = submissions.count()

            highest_score = ActivitySubmission.objects.filter(
                student=request.user,
                activity=activity
            ).aggregate(Max('score'))['score__max'] or 0

            highest_returned_submission = None
            highest_feedback = None

            quiz_score = None
            quiz_feedback = None
            if return_quiz_submission:
                quiz_score = return_quiz_submission.score
                quiz_feedback = return_quiz_submission.feedback
            
            if highest_score is not None and highest_score > 0:
                highest_returned_submission = ActivitySubmission.objects.filter(
                    student=request.user,
                    activity=activity,
                    score=highest_score,
                    status="returned"
                ).order_by('-submitted_at').first()
                
                if highest_returned_submission:
                    highest_feedback = highest_returned_submission.feedback
                else:
                    top_submission = ActivitySubmission.objects.filter(
                        student=request.user,
                        activity=activity,
                        score=highest_score
                    ).order_by('-submitted_at').first()
                    highest_feedback = top_submission.feedback if top_submission else None

            activity_submissions = ActivitySubmission.objects.filter(
                activity=activity, 
                student=request.user
            ).order_by('-submitted_at')

            if action_type == "activity_details":
                return render(request, "c_activities/compiler/partials/activity_details.html", {
                    "activity": activity,
                    "activity_submissions": activity_submissions,
                    "submission_count": submission_count,
                    "highest_score": highest_score,
                    "highest_feedback": highest_feedback,
                    "highest_returned_submission": highest_returned_submission,
                    "quiz_score": quiz_score,
                    "quiz_feedback": quiz_feedback,
                })

            return render(request, 'c_activities/compiler/student.compiler.html', {
                "activity": activity,
                "submission": submission,
                "activity_submissions": activity_submissions,
                "user_profile": user_profile,
                "subject_id": subject_id,
                "subject": subject,
                "submission_count": submission_count,
                "highest_score": highest_score,
                "highest_feedback": highest_feedback,
                "highest_returned_submission": highest_returned_submission,  # Add this
                "current_time": localtime(timezone.now()),
                "server_time": timezone.now().isoformat(),
            })

def prev_or_next_view(request):
    button_type = request.GET.get("action")
    activity_id = request.GET.get("activity_id")
    subject_id = request.GET.get("subject_id")
    current_index = int(request.GET.get("index", 0))

    activity = select_activity_by_id(activity_id)
    if not activity:
        return redirect("a_classroom:index")

    highest_score_subquery = ActivitySubmission.objects.filter(
        activity=activity,
        student=OuterRef('student')
    ).order_by('-score').values('score')[:1]
    
    activity_submissions = ActivitySubmission.objects.filter(
        activity=activity,
        student__in=activity.submissions.values('student').distinct(),
        score=Subquery(highest_score_subquery)
    ).select_related("student").order_by('student__username', '-submitted_at')

    unique_highest_submissions = []
    seen_students = set()
    for submission in activity_submissions:
        if submission.student.id not in seen_students:
            unique_highest_submissions.append(submission)
            seen_students.add(submission.student.id)
    
    if activity.type == "activity":
        unique_highest_submissions = [
            sub for sub in unique_highest_submissions 
            if sub.status in ["submitted", "returned", "In Progress"]
        ]
    
    total = len(unique_highest_submissions)

    if button_type == "next":
        current_index += 1
    elif button_type == "previous":
        current_index -= 1

    current_index = max(0, min(current_index, total - 1 if total > 0 else 0))

    submission = unique_highest_submissions[current_index] if total > 0 and current_index < total else None

    return render(request, 'c_activities/activity.partial/partials/submission.partial.html', {
        "index": current_index,
        "submission": submission,
        "activity": activity,
        "total_submissions": total,
        "subject_id": subject_id,
        "now": timezone.now(),
    })

class HtmxTemplateView(View):
    queryset = None
    template = None
    htmx_template = None
    htmx_trigger = None
    context_name = None

    def get_queryset(self):
        if callable(self.queryset):
            return self.queryset()
        return self.queryset

    def get(self, request: HttpRequest):
        data = self.get_queryset()
        trigger = request.headers.get("HX-Trigger")

        if request.headers.get("HX-Request") == "true" and trigger == self.htmx_trigger:
            return render(request, self.htmx_template, {self.context_name: data})

        return render(request, self.template, {self.context_name: data})

def get_admin_dashboard(request):
    users = User.objects.all()[0:10]
    trigger = request.headers.get("HX-Trigger")

    if request.headers.get("HX-Request") == "true" and trigger == "all-user":
        return render(request, 'a_classroom/a.admin/users/users.html', {"all_users": users})

    return render(request, 'a_classroom/a.admin/admin.html', {"all_users": users})

def get_pending_users(request):
    pending_users = User.objects.filter(is_active=False)[0:10]
    return render(request, 'a_classroom/a.admin/users/pending/pending.users.html', {"pending_users": pending_users})

def get_subject_list(request):
    subjects = Subject.objects.all().order_by('-id')[0:10]
    return render(request, 'a_classroom/a.admin/users/subject/subjects.html', {"subjects": subjects})

class AdminDashboardView(HtmxTemplateView):
    def get_queryset(self):
        return User.objects.all()
    
    template = 'a_classroom/a.admin/admin.html'
    htmx_template = 'a_classroom/a.admin/users/users.html'
    htmx_trigger = 'all-user'
    context_name = 'all_users'

def get_subject_activities(request):
    activities = Activity.objects.all().order_by('-id')[0:10]
    return render(request, 'a_classroom/a.admin/activities/activities.html', {"activities" : activities})

# def view_activity(request, activity_id):
#     activity = get_object_or_404(Activity, activity_id=activity_id)
    
#     submissions = ActivitySubmission.objects.filter(activity=activity)
    
#     students = User.objects.filter(
#         id__in=submissions.values('student').distinct()
#     )
    
#     student_averages = []
#     for student in students:
#         student_submissions = submissions.filter(student=student)
#         avg_score = student_submissions.aggregate(avg_score=Avg('score'))['avg_score']
        
#         latest_submission = student_submissions.order_by('-submitted_at').first()
        
#         student_averages.append({
#             'student': student,
#             'avg_score': round(avg_score, 2) if avg_score else 0,
#             'latest_submission': latest_submission,
#             'submission_count': student_submissions.count()
#         })
    
#     return render(request, 'a_classroom/a.admin/activities/view_activity.html', {
#         "activity": activity,
#         "student_averages": student_averages
#     })

# def view_activity(request, activity_id):
#     activity = get_object_or_404(Activity, activity_id = activity_id)
#     submissions = ActivitySubmission.objects.filter(activity=activity).all()
#     return render(request, 'a_classroom/a.admin/activities/view_activity.html', {"activity" : activity, "submissions" : submissions})
# class PendingUsersView(HtmxTemplateView):
#     def get_queryset(self):
#         return User.objects.filter(is_active=False)
    
#     template = 'a_classroom/a.admin/admin.html'
#     htmx_template = 'a_classroom/a.admin/users/pending/pending.users.html'
#     htmx_trigger = 'pending-users'
#     context_name = 'pending_users'

# class SubjectListView(HtmxTemplateView):
#     def get_queryset(self):
#         return Subject.objects.all()
    
#     template = 'a_classroom/a.admin/admin.html'
#     htmx_template = 'a_classroom/a.admin/users/subject/subjects.html'
#     htmx_trigger = 'subjects'
#     context_name = 'subjects'

def view_activity(request, activity_id):
    activity = get_object_or_404(Activity, activity_id=activity_id)
    
    # Get all students who have submitted to this activity using the correct related name
    students_with_submissions = User.objects.filter(
        activity_submissions__activity=activity  # Changed from activitysubmission__ to activity_submissions__
    ).distinct()
    
    # Calculate latest score per student and overall average
    student_scores = []
    all_scores = []
    
    for student in students_with_submissions:
        # Get latest submission for this student
        latest_submission = ActivitySubmission.objects.filter(
            activity=activity,
            student=student
        ).order_by('-submitted_at').first()
        
        if latest_submission:
            if latest_submission.score is not None:
                latest_score = latest_submission.score
                all_scores.append(latest_score)
            
            student_scores.append({
                'student': student,
                'latest_score': latest_submission.score,
                'latest_submission': latest_submission,
                'submitted_at': latest_submission.submitted_at,
            })
        else:
            # This shouldn't happen since we filtered by activity_submissions__activity
            # but keeping it for safety
            student_scores.append({
                'student': student,
                'latest_score': None,
                'latest_submission': None,
                'submitted_at': None,
            })
    
    # Calculate overall average of latest scores
    overall_average = sum(all_scores) / len(all_scores) if all_scores else 0
    
    # Get average of ALL submissions (not just latest per student)
    all_submissions_scores = ActivitySubmission.objects.filter(
        activity=activity
    ).exclude(score=None).values_list('score', flat=True)
    
    average_all_submissions = sum(all_submissions_scores) / len(all_submissions_scores) if all_submissions_scores else 0
    
    # Count total submissions
    total_submissions = ActivitySubmission.objects.filter(activity=activity).count()
    
    return render(request, 'a_classroom/a.admin/activities/view_activity.html', {
        "activity": activity,
        "student_data": student_scores,  # Changed from student_scores to student_data to match template
        "overall_average": round(overall_average, 2),
        "average_all_submissions": round(average_all_submissions, 2),
        "total_students": len(student_scores),
        "total_submissions": total_submissions,
    })

class ApproveUserAdminView(View):
    def post(self, request, user_id):
        user = get_object_or_404(User, id=user_id)

        trigger = request.headers.get("HX-Trigger")

        if request.headers.get("HX-Request") == "true" and trigger == "approve-button":
            user.is_active = True
            user.save()

            # Send approval email
            subject = "Your Account Has Been Approved"
            message = f"""Hello {user.first_name},

Your account has been approved by the admin.

You can now login into your account.

Best regards,  
CodeCheckAI Team
"""
            try:
                connection = get_connection()
                connection.open()
                
                send_mail(
                    subject, 
                    message, 
                    settings.DEFAULT_FROM_EMAIL, 
                    [user.email],
                    connection=connection
                )
                connection.close()
                
                print("✅ Approval email sent successfully")
                messages.success(request, "Approval email sent successfully")
            except Exception as e:
                print(f"❌ Email send failed: {e}")
                
            pending_users = User.objects.filter(is_active=False)
            return render(request, "a_classroom/a.admin/users/pending/partial/pending.table.html", {"pending_users" : pending_users})

        return redirect("a_classroom:index")


def delete_account_creation(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if not user:
        return redirect("a_classroom:index")
    user.delete()
    pending_users = User.objects.filter(is_active=False)
    return render(request, "a_classroom/a.admin/users/pending/partial/pending.table.html", {"pending_users" : pending_users})