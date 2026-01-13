from django.shortcuts import render, redirect, get_object_or_404
from .models import Activity, ActivitySubmission, ActivityExample, ActivityCriteria
from a_classroom.models import Subject
from a_classroom.views import select_activity_by_id, select_subject_by_id, get_submission_by_id
from b_enrollment.models import UserProfile
from django.views import View
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.contrib import messages
from django.conf import settings
from openai import OpenAI
import google.generativeai as genai
from datetime import datetime
import re, json, requests, time
from django.utils.timezone import localtime, make_aware
from django.utils import timezone
import traceback

# Create your views here.
client = OpenAI(api_key=settings.OPENAI_API_KEY)

def prompt_to_aimodel_gpt4o(prompt, activity_id):
    responses = []
    for i in range(5):
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful AI assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100,
            temperature=0.7,
            n=1
        )
        
        response_text = response.choices[0].message.content
        responses.append({'generated_text': response_text})
    
    activity = select_activity_by_id(activity_id)
    if not activity:
        return redirect("a_classroom:index")
    
    saved_examples = []
    for output in responses:
        example = ActivityExample.objects.create(
            activity=activity,
            example_text=output['generated_text']
        )
        saved_examples.append(example.example_text)

    return saved_examples

def evaluate_student_code_with_openai(code, language, instruction="", examples="", criterias=None, max_score=100):
    if not criterias or len(criterias) < 3:
        criterias = [0, 0, 0]

    prompt = f"""
    ## TASK
    Evaluate student code using these criteria weights:
    - Correctness: {criterias[0]}%
    - Syntax: {criterias[1]}%
    - Structure: {criterias[2]}%

    ## INPUTS
    **Instruction:** {instruction if instruction.strip() != "" else "No additional instructions provided."}
    **Language:** {language}
    **Max Score:** {max_score}
    **Examples:** {examples if examples else "None"}

    **Code:**
    {code}

    ## REQUIREMENTS
    1. Calculate final score (1-{max_score}) using weighted criteria
    2. Include criteria percentages in response
    3. Provide score breakdown per criterion
    4. Compare code to instructions and identify issues
    5. Give improvement hints (not full solutions)
    6. Consider language context

    ## OUTPUT FORMAT (STRICT)
    <grading>
    Grading: [score]/{max_score}
    Insight: [1-2 sentence insight]

    **Correctness ({criterias[0]}%):** [x]/{max_score}
    • Explanation: [Why this score? What's working/not working?]

    **Syntax ({criterias[1]}%):** [y]/{max_score}
    • Explanation: [Syntax issues found]

    **Structure ({criterias[2]}%):** [z]/{max_score}
    • Explanation: [Structure/readability issues]

    **Total:** [total]/{max_score}

    **Main Issues vs Instructions:**
    • [Issue 1]
    • [Issue 2]

    **Improvement Hints:**
    • [Hint 1 - specific guidance]
    • [Hint 2 - focused suggestion]
    </grading>
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a Python and Java code reviewer."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=500,
        temperature=0.5,
    )

    return response.choices[0].message.content

def evaluate_student_code_with_openai_for_playground(code):

    prompt = f"""
    Code to evaluate:
    {code}
    Do not put acknowledgement into my command or anything just say something like Here's a structured review of the provided code or something.
    ALSO include what is wrong with the code and how to improve it but do not give the whole code to solve the task at hand but instead give a hint of some sort just to help them improve it.
    Format your response exactly as follows:

    Here's a structured review of the provided code:

    ***Syntax Error***.
    [Your sentence here.]

    ***Completion of Code***.
    [Your sentence here.]

    ***Logic and Functionality***.
    [Your sentence here.]

    ***Code Readability and Structure***.
    [Your sentence here.]

    ***Best Practices and Suggestions***.
    [Your sentence here.]

    Rules:
    1.  Start a new line immediately after each colon (`:`) for the main headers (e.g., "Here's a structured review...").
    2.  Do not write any text on the same line after a colon for those main headers.
    3.  Each category (like `***Syntax Error***`) must be on its own line.
    4.  For each category, write only one sentence directly beneath it.
    5.  Use only the specified category titles. Do not add numbers (1, 2, etc.) or markdown formatting like `###` or `'''`.
    6.  Do not add any other sections, comments, or concluding remarks outside this structure.
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a Python and Java code reviewer."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=500,
        temperature=0.5,
    )

    return response.choices[0].message.content

@method_decorator(never_cache, name='dispatch')
class CreateActivityView(View):
    def get(self, request):
        action_type = request.GET.get("action")
        if action_type == "create-activity":
            
            subject_id = request.GET.get("subject_id")
            if not subject_id:
                return HttpResponse("Missing subject ID", status=400)
            return render(
                request,
                "c_activities/activity/create_activity.html",
                {"subject_id": subject_id,
                "current_time" : localtime(timezone.now()),
                "server_time": localtime(timezone.now())},
            )
        return redirect("a_classroom:index")

    def post(self, request):
        action_type = request.POST.get("action")
        criterias = request.POST.getlist("criteria")
        subject_id = request.POST.get("subject_id")
        due_at_raw = request.POST.get("id_due_at")

        values = []
        for val in criterias:
            try:
                values.append(int(val) if val else 0)
            except (ValueError, TypeError):
                values.append(0)
        
        total = sum(values)

        if total < 100 or total > 100:
            messages.error(request, f"Criteria total cannot be less than or exceed 100%")
            response = HttpResponse()
            response["HX-Redirect"] = f"/c/subject/{subject_id}/"
            return response

        due_at = None
        if due_at_raw:
            try:
                due_at = datetime.strptime(due_at_raw, "%Y-%m-%dT%H:%M")
                due_at = make_aware(due_at)

                due_at_local = localtime(due_at)
                current_local = localtime(timezone.now())

                if due_at_local <= current_local:
                    messages.error(request, "Due date must be from today/now onwards")
                    response = HttpResponse()
                    response["HX-Redirect"] = f"/c/subject/{subject_id}/"
                    return response

            except ValueError:
                messages.error(request, "Invalid date format. Use YYYY-MM-DDTHH:MM")
                response = HttpResponse()
                response["HX-Redirect"] = f"/c/subject/{subject_id}/"
                return response

        if not request.POST.get("processing"):
            return render(request, "c_activities/activity/partial/progress_bar.html")
        else:
            return self.process_activity_creation(request)

    
    def process_activity_creation(self, request):
        try:
            subject_id = request.POST.get("subject_id")
            activity_type = request.POST.get("type")
            language_type = request.POST.get("language")
            title = request.POST.get("id_title")
            description = request.POST.get("id_description")
            max_score = request.POST.get("id_max_score")
            due_at_raw = request.POST.get("id_due_at")
            criterias = request.POST.getlist("criteria")

            if (not subject_id or not activity_type or not language_type or not title or not description or 
                not max_score or not due_at_raw or not criterias or
                subject_id.strip() == "" or activity_type.strip() == "" or language_type.strip() == "" or
                language_type.strip() == "" or title.strip() == "" or description.strip() == "" or 
                max_score.strip() == "" or due_at_raw.strip() == ""):
                
                messages.error(request, "Missing required fields")
                return redirect(f"/c/subject/{subject_id}")
            
            due_at = None
            if due_at_raw:
                try:
                    due_at = datetime.strptime(due_at_raw, "%Y-%m-%dT%H:%M")
                    due_at = make_aware(due_at)

                    due_at_local = localtime(due_at)
                    current_local = localtime(timezone.now())

                    if due_at_local <= current_local:
                        messages.error(request, "Due date must be in the future")
                        return redirect(f"/a/?action=create-activity&subject_id={subject_id}")

                except ValueError:
                    messages.error(request, "Invalid date format. Use YYYY-MM-DDTHH:MM")
                    return redirect(f"/a/?action=create-activity&subject_id={subject_id}")

            values = []
            for val in criterias:
                try:
                    values.append(int(val) if val else 0)
                except (ValueError, TypeError):
                    values.append(0)
            
            total = sum(values)

            if total < 100 or total > 100:
                messages.error(request, f"Criteria total cannot be less than or exceed 100%")
                response = HttpResponse()
                response["HX-Redirect"] = f"/c/subject/{subject_id}/"
                return response


            if not all([subject_id, activity_type, title]):
                messages.error(request, "Missing required fields")
                return redirect(f"/a/?action=create-activity&subject_id={subject_id}")

            subject = select_subject_by_id(subject_id)
            if not subject:
                messages.error(request, "Subject not found")
                return redirect("a_classroom:index")

            activity = Activity.objects.create(
                subject=subject,
                title=title,
                description=description or "",
                language=language_type,
                max_score=float(max_score) if max_score else 0.0,
                due_at=due_at,
                type=activity_type,
            )

            for criteria in criterias:
                if criteria and criteria.strip():
                    ActivityCriteria.objects.create(
                        activity=activity, text=criteria.strip()
                    )

            try:
                code_examples = prompt_to_aimodel_gpt4o(description, activity.activity_id)
            except Exception as e:
                print(f"AI model failed: {e}")

            messages.success(request, "Activity created successfully!")
            response = HttpResponse()
            response["HX-Redirect"] = f"/c/activity/{activity.activity_id}/?subject_id={subject_id}&type={activity_type}"
            return response

        except Exception as e:
            
            messages.error(request, f"Error creating activity: {str(e)}")
            return redirect(f"/a/?action=create-activity&subject_id={subject_id}")

class StudentGradeView(View):
	def get(self, request):
		submission_id = request.GET.get("submission_id")
		submission = get_submission_by_id(submission_id)

		return render(request, "c_activities/activity.partial/student.sumission.html", {"sumission" : submission})

def get_activity_examples(activity):
	examples = []
	example_text = ActivityExample.objects.filter(activity=activity)
	for example in example_text:
		examples.append(example.example_text)

	return examples

def get_activity_criterias(activity):
	criterias = []
	criterias_text = ActivityCriteria.objects.filter(activity=activity)
	for criteria in criterias_text:
		criterias.append(criteria.text)
	
	return criterias

class EditActivityView(View):
    def get(self, request, activity_id):
        activity = select_activity_by_id(activity_id)
        if not activity:
            messages.error(request, "Activity not found")
            return redirect("a_classroom:index")

        return render(request, "c_activities/edit.activity/edit.activity.html", {"activity": activity})

    def post(self, request, activity_id):
        activity = select_activity_by_id(activity_id)
        if not activity:
            messages.error(request, "Activity not found")
            return redirect("a_classroom:index")

        title = request.POST.get("title")
        description = request.POST.get("description")
        max_score = request.POST.get("max_score")
        due_at_raw = request.POST.get("due_at")
        
        if not all([title, description, max_score, due_at_raw]):
            messages.error(request, "All fields are required")
            return redirect(f"/c/activity/{activity.activity_id}/?subject_id={activity.subject.subject_id}")

        due_at = None
        try:
            due_at = datetime.strptime(due_at_raw, "%Y-%m-%dT%H:%M")
            due_at = make_aware(due_at)
            
            if due_at <= timezone.now():
                messages.error(request, "Due date must be in the future")
                return redirect(f"/c/activity/{activity.activity_id}/?subject_id={activity.subject.subject_id}")
                
                
        except ValueError:
            messages.error(request, "Invalid date format. Use YYYY-MM-DDTHH:MM")
            return redirect(f"/c/activity/{activity.activity_id}/?subject_id={activity.subject.subject_id}")
            
        activity.title = title
        activity.max_score = max_score
        activity.due_at = due_at

        if description != activity.description:
            activity.description = description
            activity.save()
            
            try:
                ActivityExample.objects.filter(activity=activity).delete()
                prompt_to_aimodel_gpt4o(description, activity.activity_id)
            except Exception as e:
                print(f"AI model failed: {e}")
        else:
            activity.description = description
            activity.save()

        messages.success(request, "Activity updated successfully!")
        return redirect(f"/c/activity/{activity.activity_id}/?subject_id={activity.subject.subject_id}")

class EditGradeView(View):
    def get(self, request, submission_id):
        submission = get_submission_by_id(submission_id)
        if not submission:
            return redirect("a_classroom:index")
        return render(request, 'c_activities/activity.partial/partials/edit_score.html', {
			"submission": submission
		})

    def post(self, request, submission_id):
        button_type = request.POST.get("action")
        new_score = request.POST.get("new_score")
        subject_id = request.POST.get("subject_id")
        activity_id = request.POST.get("activity_id")

        submission = get_submission_by_id(submission_id)
        if not submission:
            return redirect("a_classroom:index")

        if button_type == "confirm":
            submission.score = new_score
            submission.save()
            response = HttpResponse()
            response["HX-Redirect"] = f"/c/activity/{activity_id}/?subject_id={subject_id}"
            return response
        elif button_type == "cancel":
            response = HttpResponse()
            response["HX-Redirect"] = f"/c/activity/{activity_id}/?subject_id={subject_id}"
            return response
        else:
            return redirect("a_classroom:index")

class EditInsightView(View):
    def get(self, request, submission_id):
        submission = get_submission_by_id(submission_id)
        if not submission:
            return redirect("a_classroom:index")

        return render(request, "c_activities/activity.partial/partials/edit_insight.html", {"submission": submission})

    def post(self, request, submission_id):
        button_type = request.POST.get("action")
        new_insight = request.POST.get("new_insight")
        subject_id = request.POST.get("subject_id")
        activity_id = request.POST.get("activity_id")

        submission = get_submission_by_id(submission_id)
        if not submission:
            return redirect("a_classroom:index")
        
        if button_type == "confirm":
            submission.feedback = new_insight
            submission.save()
            # return HttpResponse(new_insight)
            response = HttpResponse()
            response["HX-Redirect"] = f"/c/activity/{activity_id}/?subject_id={subject_id}"
            return response

        elif button_type == "cancel":
            # return HttpResponse(submission.feedback)
            response = HttpResponse()
            response["HX-Redirect"] = f"/c/activity/{activity_id}/?subject_id={subject_id}"
            return response
        else:
            return redirect("a_classroom:index")

def return_submission(request, submission_id):
    action_type = request.POST.get("action")

    submission = get_submission_by_id(submission_id)
    if not submission:
        return redirect("a_classroom:index")

    submission.status = 'returned'
    submission.save()

    activity_id = submission.activity.activity_id
    subject_id = submission.activity.subject.subject_id
    activity_type = submission.activity.type

    response = HttpResponse()
    response["HX-Redirect"] = f"/c/activity/{activity_id}/?subject_id={subject_id}&type={activity_type}"
    return response

def delete_activity(request, activity_id):
	activity = select_activity_by_id(activity_id)
	if not activity:
		return redirect("a_classroom:index")

	subject_id = activity.subject.subject_id

	activity.delete()

	response = HttpResponse()
	response["HX-Redirect"] = f"/c/subject/{subject_id}/?from=/c/"
	return response

def criteria_checking_function(request):
    if request.method == "POST":
        criteria_values = request.POST.getlist("criteria")

        values = []
        for val in criteria_values:
            try:
                values.append(int(val) if val else 0)
            except (ValueError, TypeError):
                values.append(0)
        
        total = sum(values)

        if total == 100:
            return HttpResponse(f'Total: <span class="font-bold text-green-600">{total}% ✓</span>')
        elif total > 100:
            return HttpResponse(f'Total: <span class="font-bold text-red-600">{total}% (Over 100%)</span>')
        else:
            return HttpResponse(f'Total: <span class="font-bold text-yellow-600">{total}% (Need {100-total}% more)</span>')
    
    return HttpResponse('')