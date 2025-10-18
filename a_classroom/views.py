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

def index(request):
    if not hasattr(request.user, 'userprofile'):
        messages.error(request, "Your account is incomplete. Please contact the administrator.")
        return redirect('register:login')

    if request.user.userprofile.role == "Admin":
        if request.headers.get("HX-Request") == "true":
            return render(request, 'a_classroom/sidebar/sidebar.html')
        return render(request, 'a_classroom/a.admin/admin.html')

    elif request.user.userprofile.role == "Instructor":
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
                    print("debugging one")
                    return self.process_subject_creation(request)

            return self.process_subject_creation(request)
            
        form = CreateSubjectForm()
        return render(request, 'a_classroom/create_subject.html', {"form": form})

    def process_subject_creation(self, request):
        print("You triggered this function")
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
            else:
                subject = Subject.objects.create(
                    instructor=request.user,
                    course_code=course_code,
                    section=section,
                    name=name
                )
                messages.success(request, f"{course_code} for section {section_name} has been created.")
            
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

def about(request):
    return render(request, 'a_classroom/about.html')

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
            filters = {"activity": activity}
            if activity.type == "activity":
                filters["status__in"] = ["submitted", "returned"]

            activity_submissions = ActivitySubmission.objects.filter(**filters).select_related("student")
            return render(request, 'c_activities/activity.partial/student.submission.html', {
                "activity" : activity,
                "user_profile": user_profile,
                "activity_submissions": activity_submissions,
                "subject_id": subject_id,
            })

        elif user_profile.role == "Student":
            action_type = request.GET.get("action")
            submissions = activity.submissions.filter(student=request.user).order_by("-submitted_at")
            submission = submissions.filter(status__in=["submitted", "returned"]).first()
            if not submission:
                submission = submissions.first()

            submission_count = submissions.count()

            highest_score = ActivitySubmission.objects.filter(
                student=request.user,
                activity=activity
            ).aggregate(Max('score'))['score__max'] or 0


            highest_feedback = None
            if highest_score is not None:
                top_submission = ActivitySubmission.objects.filter(
                    student=request.user,
                    activity=activity,
                    score=highest_score
                ).first()
                highest_feedback = top_submission.feedback if top_submission else None

            activity_submissions = []
            
            if activity:
                activity_submission = ActivitySubmission.objects.filter(activity=activity, student=request.user).first()
                if activity_submission:
                    activity_submissions = [activity_submission]
                
            if activity.type == "quiz":
                max_attempt = activity.max_attempt if activity.max_attempt is not None else 0
                if submission_count >= max_attempt:
                    submit = ActivitySubmission.objects.filter(activity=activity, student=request.user)
                    submit.update(status="returned")


            if action_type == "activity_details":
                return render(request, "c_activities/compiler/partials/activity_details.html", {
                    "activity" : activity,
                    "activity_submissions" : activity_submissions,
                    "submission_count" : submission_count,
                    "highest_score" : highest_score,
                    "highest_feedback" : highest_feedback
                })

            return render(request, 'c_activities/compiler/student.compiler.html', {
                "activity": activity,
                "submission" : submission,
                "activity_submissions": activity_submissions,
                "user_profile": user_profile,
                "subject_id": subject_id,
                "subject": subject,
                "submission_count" : submission_count
            })

        return HttpResponse("Unhandled request case.", status=400)

def prev_or_next_view(request):
    button_type = request.GET.get("action")
    activity_id = request.GET.get("activity_id")
    current_index = int(request.GET.get("index", 0))

    activity = select_activity_by_id(activity_id)
    if not activity:
        return redirect("a_classroom:index")

    filters = {"activity": activity}
    if activity.type == "activity":
        filters["status__in"] = ["submitted", "returned"]

    activity_submissions = ActivitySubmission.objects.filter(**filters).select_related("student")
    total = activity_submissions.count()

    if button_type == "next":
        current_index += 1
    elif button_type == "previous":
        current_index -= 1

    current_index = max(0, min(current_index, total - 1))

    submission = activity_submissions[current_index] if total > 0 else None

    return render(request, 'c_activities/activity.partial/partials/submission.partial.html', {
        "index": current_index,
        "submission": submission,
        "activity": activity,
        "now": timezone.now(),
    })

class HtmxTemplateView(View):
    queryset = None
    template = None
    htmx_template = None
    htmx_trigger = None
    context_name = None

    def get(self, request: HttpRequest):
        data = self.queryset() if callable(self.queryset) else self.queryset
        trigger = request.headers.get("HX-Trigger")

        if request.headers.get("HX-Request") == "true" and trigger == self.htmx_trigger:
            return render(request, self.htmx_template, {self.context_name: data})

        return render(request, self.template, {self.context_name: data})

class AdminDashboardView(HtmxTemplateView):
    queryset = User.objects.all
    template = 'a_classroom/a.admin/admin.html'
    htmx_template = 'a_classroom/a.admin/users/users.html'
    htmx_trigger = 'all-user'
    context_name = 'all_users'

class PendingUsersView(HtmxTemplateView):
    queryset = lambda self: User.objects.filter(is_active=False)
    template = 'a_classroom/a.admin/users/pending.html'
    htmx_template = 'a_classroom/a.admin/users/pending/pending.users.html'
    htmx_trigger = 'pending'
    context_name = 'pending_users'

class SubjectListView(HtmxTemplateView):
    queryset = Subject.objects.all
    template = 'a_classroom/a.admin/users/subject.html'
    htmx_template = 'a_classroom/a.admin/users/subject/subjects.html'
    htmx_trigger = 'all-subject'
    context_name = 'subjects'

class ArchivedSubjectListView(HtmxTemplateView):
    queryset = lambda self: Subject.objects.filter(is_archived=True)
    template = 'a_classroom/a.admin/users/archived.html'
    htmx_template = 'a_classroom/a.admin/users/subject/archived.subjects.html'
    htmx_trigger = 'archived'
    context_name = 'archived_subjects'

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
Admin Team
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
                messages.error(request, f"Email send failed : {e}")
                
            pending_users = User.objects.filter(is_active=False)
            return render(
                request,
                'a_classroom/a.admin/users/pending/pending.users.html',
                {"pending_users": pending_users}
            )

        return redirect("a_classroom:index")


def delete_account_creation(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if not user:
        return redirect("a_classroom:index")
    user.delete()
    pending_users = User.objects.filter(is_active=False)
    return render(request, "a_classroom/a.admin/users/pending/pending.users.html", {"pending_users" : pending_users})