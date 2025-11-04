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
from django.utils import timezone
from openai import OpenAI
import google.generativeai as genai
from datetime import datetime
import re, json, requests, time
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

def evaluate_student_code_with_openai(code, instruction="", examples="", criterias=None, max_score=100):
    if not criterias or len(criterias) < 3:
        criterias = [0, 0, 0]

    prompt = f"""
    Evaluate the following student code according to these criteria and weights:
    Criteria and Weights:
    - Correctness (logical accuracy and whether the code performs the intended task): {criterias[0]}%
    - Syntax (syntax errors, formatting issues): {criterias[1]}%
    - Structure (organization, readability, code design): {criterias[2]}%

    Instruction: {instruction if instruction.strip() != "" else "No additional instructions provided."}

    Code to evaluate:
    {code}

    Example solutions for reference:
    {examples if examples else "No example solutions provided."}

    Please:
    - Use the weights above to calculate a final grade between 1 and {max_score}.
    - Provide a short insightful evaluation comment.
    - Format the output as:
    <grading>Grading: your_score_here
    Insight: your_insight_here
    ALSO include what is wrong with the code compared to the instruction and how to improve it but do not give the whole code to solve the task at hand but instead give a hint of some sort just to help them improve it.
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
    Finally, Can you fix the format of your response.
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
                {"subject_id": subject_id},
            )
        return redirect("a_classroom:index")

    def post(self, request):
        action_type = request.POST.get("action")
        criterias = request.POST.getlist("criteria")
        subject_id = request.POST.get("subject_id")
        values = []
        for val in criterias:
            try:
                values.append(int(val) if val else 0)
            except (ValueError, TypeError):
                values.append(0)
        
        total = sum(values)

        if total > 100:
            messages.error(request, f"Criteria total cannot exceed 100%")
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
            title = request.POST.get("id_title")
            description = request.POST.get("id_description")
            max_score = request.POST.get("id_max_score")
            due_at_raw = request.POST.get("id_due_at")
            criterias = request.POST.getlist("criteria")

            if (not subject_id or not activity_type or not title or not description or 
                not max_score or not due_at_raw or not criterias or
                subject_id.strip() == "" or activity_type.strip() == "" or 
                title.strip() == "" or description.strip() == "" or 
                max_score.strip() == "" or due_at_raw.strip() == ""):
                
                messages.error(request, "Missing required fields")
                return redirect(f"/c/subject/{subject_id}")

            values = []
            for val in criterias:
                try:
                    values.append(int(val) if val else 0)
                except (ValueError, TypeError):
                    values.append(0)
            
            total = sum(values)

            if total > 100:
                messages.error(request, f"Criteria total cannot exceed 100%")
                response = HttpResponse()
                response["HX-Redirect"] = f"/c/subject/{subject_id}/"
                return response


            if not all([subject_id, activity_type, title]):
                messages.error(request, "Missing required fields")
                return redirect(f"/a/?action=create-activity&subject_id={subject_id}")

            if activity_type == "quiz":
                raw_attempt = request.POST.get("id_max_attempt")
                max_attempt = int(raw_attempt) if raw_attempt else 3
            else:
                max_attempt = None

            subject = select_subject_by_id(subject_id)
            if not subject:
                messages.error(request, "Subject not found")
                return redirect("a_classroom:index")

            due_at = None
            if due_at_raw:
                try:
                    due_at = datetime.strptime(due_at_raw, "%Y-%m-%dT%H:%M")
                except ValueError:
                    messages.error(request, "Invalid date format. Use YYYY-MM-DDTHH:MM")
                    return redirect(f"/a/?action=create-activity&subject_id={subject_id}")

            filters = {
                "subject": subject,
                "title": title,
                "type": activity_type,
            }
            existing_activity = Activity.objects.filter(**filters).first()
            if existing_activity:
                messages.error(request, "Activity with this title already exists for this subject.")
                return redirect(f"/a/?action=create-activity&subject_id={subject_id}")

            activity = Activity.objects.create(
                subject=subject,
                title=title,
                description=description or "",
                max_score=float(max_score) if max_score else 0.0,
                max_attempt=max_attempt,
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

        submission = get_submission_by_id(submission_id)
        if not submission:
            return redirect("a_classroom:index")

        if button_type == "confirm":
            submission.score = new_score
            submission.save()
            return HttpResponse(new_score)

        elif button_type == "cancel":
            return HttpResponse(submission.score)
        else:
            return redirect("a_classroom:index")

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
			return redirect("a_classroom:index")

		return render(request, "c_activities/edit.activity/edit.activity.html", {"activity" : activity})

	def post(self, request, activity_id):
		activity = select_activity_by_id(activity_id)
		if not activity:
			return redirect("a_classroom:index")

		activity.title = request.POST.get("title")
		description = request.POST.get("description")
		if description != activity.description:
			activity.description = description
			ActivityExample.objects.filter(activity=activity).delete()
			prompt_to_aimodel_gpt4o(description, activity.activity_id)
		else:
			activity.description = description

		activity.max_score = request.POST.get("max_score")
		activity.due_at = request.POST.get("due_at")
		activity.save()

		return redirect(f"/c/activity/{activity.activity_id}/?subject_id={activity.subject.subject_id}")

class EditInsightView(View):
	def get(self, request, submission_id):
		submission = get_submission_by_id(submission_id)
		if not submission:
			return redirect("a_classroom:index")

		return render(request, "c_activities/activity.partial/partials/edit_insight.html", {"submission" : submission})

	def post(self, request, submission_id):
		button_type = request.POST.get("action")
		new_insight = request.POST.get("new_insight")

		submission = get_submission_by_id(submission_id)
		if not submission:
			return redirect("a_classroom:index")
		
		if button_type == "confirm":
			submission.feedback = new_insight
			submission.save()
			return HttpResponse(new_insight)

		elif button_type == "cancel":
			return HttpResponse(submission.feedback)
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