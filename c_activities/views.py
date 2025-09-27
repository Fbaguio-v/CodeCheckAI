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
from mysite.wsgi import pipe

# Create your views here.
client = OpenAI(api_key=settings.OPENAI_API_KEY)
genai.configure(api_key=settings.GEMINI_API_KEY)
gemini_model = "gemini-2.5-flash-lite"

def prompt_to_aimodel(prompt, activity_id):
    outputs = pipe(prompt, max_length=100, num_return_sequences=5, do_sample=True, top_k=50, truncation=True)

    activity = select_activity_by_id(activity_id)
    if not activity:
        return redirect("a_classroom:index")
    
    saved_examples = []
    for output in outputs:
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
    Feedback:
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

def evaluate_student_code_with_gemini(code, instruction="", examples="", criterias=None, max_score=100):
    if not criterias or len(criterias) < 3:
        criterias = [0, 0, 0]

    prompt = f"""
You are a strict Python and Java code reviewer. 
You must ONLY evaluate code in Python or Java. 
If asked to do anything unrelated, politely refuse. 

Evaluate the following student code according to these criteria and weights:

Criteria and Weights:
- Correctness: {criterias[0]}%
- Syntax: {criterias[1]}%
- Structure: {criterias[2]}%

Instruction: {instruction if instruction.strip() != "" else "No additional instructions provided."}

Code to evaluate:
{code}

Example solutions for reference:
{examples if examples else "No example solutions provided."}

⚠️ REQUIRED FORMAT:
- Use the weights above to calculate a final grade between 1 and {max_score}.
- Always output in this exact format:

<grading>Grading your_score_here
Insight: your_insight_here

For example:
<grading>Grading {max_score - 15}
Insight: The code is mostly correct but missing error handling.

Do not include explanations, JSON, or anything else.
Only output in the format above.
"""

    model = genai.GenerativeModel("gemini-2.5-flash-lite")

    response = model.generate_content(
        prompt,
        generation_config={
            "max_output_tokens": 500,
            "temperature": 0.5,
            "response_mime_type": "text/plain",
        }
    )

    if not response or not response.text:
        return "<grading>Grading 0\nInsight: No response from Gemini."

    text = response.text.strip()
    print("Gemini raw response:", repr(text))

    match = re.search(
        r"<grading>\s*Grading\s*([\d\.]+)(?:\s*/\s*\d+)?\s*[\r\n]+Insight:\s*(.+)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if match:
        grading = match.group(1).strip()
        insight = match.group(2).strip()
        return f"Grading {grading}\nInsight: {insight}"

    if text.startswith("{") and text.endswith("}"):
        try:
            data = json.loads(text)
            if "grading" in data and "insight" in data:
                return f"Grading {data['grading']}\nInsight: {data['insight']}"
        except Exception:
            pass

    return f"<grading>Grading 0\nInsight: (Unparsed) {text}"

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
        if action_type == "create_activity":

            subject_id = request.POST.get("subject_id")
            activity_type = request.POST.get("type")
            title = request.POST.get("id_title")
            description = request.POST.get("id_description")
            max_score = request.POST.get("id_max_score")
            due_at_raw = request.POST.get("id_due_at")
            criterias = request.POST.getlist("criteria")

            if activity_type == "quiz":
                raw_attempt = request.POST.get("id_max_attempt")
                max_attempt = int(raw_attempt) if raw_attempt else 3
            else:
                max_attempt = None

            subject = select_subject_by_id(subject_id)
            if not subject:
                return redirect("a_classroom:index")

            due_at = None
            if due_at_raw:
                try:
                    due_at = datetime.strptime(due_at_raw, "%Y-%m-%dT%H:%M")
                except ValueError:
                    return HttpResponse(
                        "Invalid date format. Expected YYYY-MM-DDTHH:MM", status=400
                    )

            filters = {
                "subject": subject,
                "title": title,
                "description": description,
                "type": activity_type,
            }
            existing_activity = Activity.objects.filter(**filters).first()
            if existing_activity:
                messages.error(request, "Activity already exists.")
                return redirect(
                    f"{request.path}?action=create-activity&subject_id={subject_id}"
                )

            activity = Activity.objects.create(
                subject=subject,
                title=title,
                description=description,
                max_score=max_score,
                max_attempt=max_attempt,
                due_at=due_at,
                type=activity_type,
            )

            for criteria in criterias:
                if criteria.strip():
                    ActivityCriteria.objects.create(
                        activity=activity, text=criteria.strip()
                    )

            code_examples = prompt_to_aimodel(description, activity.activity_id)

            messages.success(request, "Activity created successfully.")
            return redirect("a_classroom:v", subject_id=subject.subject_id)

        return redirect("a_classroom:index")


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
			prompt_to_aimodel(description, activity.activity_id)
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
    response["HX-Redirect"] = f"/c/activity/{activity_id}/?subject_id={subject_id}&type={action_type}"
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