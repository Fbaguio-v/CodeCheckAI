from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.conf import settings
from c_activities.views import evaluate_student_code_with_openai, evaluate_student_code_with_openai_for_playground, get_activity_examples, get_activity_criterias
from c_activities.models import Activity, ActivitySubmission, ActivityExample
from a_classroom.models import Subject
from a_classroom.views import select_subject_by_id, select_activity_by_id, get_student_submission_by_id, get_submission_by_id
from django.utils import timezone
from django_user_agents.utils import get_user_agent
from django.contrib import messages
import concurrent.futures
import requests
import json
import time
import re

# Create your views here.
        
class CompilerView(View):
    def get(self, request):
        user_agent = get_user_agent(request)
        if user_agent.is_mobile or user_agent.is_tablet:
            messages.warning(request, "This platform is optimized for desktop and laptop computers. Please use a PC or laptop for the best coding experience.")
        return render(request, 'd_compiler/playground.html')

    def post(self, request):
        a_type = request.GET.get("type")
        action_type = request.POST.get("action")
        code = request.POST.get("compiler")
        subject_id = request.POST.get("subject_id")
        activity_id = request.POST.get("activity_id")
        submission_id = request.POST.get("submission_id")

        subject = None
        activity = None
        if a_type != "playground":
            subject = select_subject_by_id(subject_id)
            activity = select_activity_by_id(activity_id)
            if not subject and not activity:
                return redirect("a_classroom:index")

        student = request.user

        match action_type:
            case "turn_in":
                if not code or code.strip() == "":
                    messages.error(request, "Cannot submit empty code.")
                    response = HttpResponse()
                    response["HX-Redirect"] = f"/c/activity/{activity_id}/?subject_id={subject_id}&type=activity"
                    return response

                submission = get_student_submission_by_id(student, activity)
                
                if submission and submission.status == "submitted":
                    messages.error(request, "You have already submitted this activity.")
                    response = HttpResponse()
                    response["HX-Redirect"] = f"/c/activity/{activity_id}/?subject_id={subject_id}&type=activity"
                    return response

                instruction = activity.description
                examples = get_activity_examples(activity)
                criterias = get_activity_criterias(activity)

                evaluate = evaluate_student_code_with_openai(code, instruction, examples, criterias, activity.max_score)

                parts = evaluate.split("<grading>")
                raw_grading = parts[0]
                match = re.search(r"(\d+(?:\.\d+)?)", raw_grading)
                score = float(match.group(1)) if match else 0
                feedback = re.sub(r"Grading:.*?Insight:\s*", "", raw_grading, flags=re.DOTALL).strip()

                if submission:
                    submission.submitted_code = code
                    submission.submitted_at = timezone.now()
                    submission.feedback = feedback
                    submission.score = score
                    submission.status = "submitted"
                    submission.evaluator = "OpenAI"
                    submission.save()
                else:
                    submission = ActivitySubmission.objects.create(
                        student=student,
                        activity=activity,
                        submitted_code=code,
                        submitted_at=timezone.now(),
                        feedback=feedback,
                        score=score,
                        status="submitted",
                        evaluator="OpenAI"
                    )

                response = HttpResponse()
                response["HX-Redirect"] = f"/c/activity/{activity_id}/?subject_id={subject_id}&type=activity"
                return response
            case "save_draft":
                existing = get_student_submission_by_id(student, activity)
                
                if existing and existing.status == "submitted":
                    messages.error(request, "You have already submitted this activity.")
                    response = HttpResponse()
                    response["HX-Redirect"] = f"/c/activity/{activity_id}/?subject_id={subject_id}&type=activity"
                    return response
                
                submission, created = ActivitySubmission.objects.update_or_create(
                    student=student,
                    activity=activity,
                    defaults={
                        "saved_code": code,
                        "status": "in_progress"
                    }			
                )
                
                if created:
                    messages.success(request, "Draft saved successfully!")
                else:
                    messages.success(request, "Draft updated successfully!")
                
                response = HttpResponse()
                response["HX-Redirect"] = f"/c/activity/{activity_id}/?subject_id={subject_id}&type=activity"
                return response
            case "unsubmit":
                submission = get_submission_by_id(submission_id)
                if not submission:
                    response = HttpResponse()
                    response["HX-Redirect"] = f"/c/activity/{activity_id}/?subject_id={subject_id}&type=activity"
                    return response

                if submission.submitted_code:
                    submission.saved_code = submission.submitted_code
                submission.status = "in_progress"
                submission.save()
                
                response = HttpResponse()
                response["HX-Redirect"] = f"/c/activity/{activity_id}/?subject_id={subject_id}&type=activity"
                return response
            case "run_code":
                language_id = request.POST.get("language_id")
                try:
                    language_id = int(language_id)
                except (ValueError, TypeError):
                    return HttpResponse("Invalid language ID", status=400)

                if code.strip() == "":
                    messages.error(request, "Code cannot be empty.")
                    response = HttpResponse()
                    response["HX-Redirect"] = reverse('a_classroom:v', args=[subject_id])
                    return response

                judge_payload = {
                    "source_code": code,
                    "language_id": language_id,
                    "stdin": "",
                }

                if a_type == "quiz":
                    if code.strip() == "":
                        response = HttpResponse()
                        response["HX-Redirect"] = f"/c/activity/{activity_id}/?subject_id={subject_id}&type=activity"
                        return response

                    submission_count = ActivitySubmission.objects.filter(student=student, activity=activity).count()
                    if submission_count >= activity.max_attempt:
                        return HttpResponse("You have reached the maximum number of attempts", status=400)

                    submission = ActivitySubmission.objects.create(
                        student=student,
                        activity=activity,
                        submitted_code=code,
                        saved_code="",
                        attempt=submission_count + 1,
                        status="in_progress"
                    )
                
                try:
                    response = requests.post(
                        f"{settings.JUDGE0_URL}?base64_encoded=false&wait=false",
                        headers=settings.HEADERS,
                        json=judge_payload
                    )
                    response_data = response.json()
                    token = response_data.get("token")

                    if not token:
                        return HttpResponse("Submission failed", status=500)

                    result_url = f"{settings.JUDGE0_URL}/{token}/?base64_encoded=false"
                    for _ in range(10):
                        result_response = requests.get(result_url, headers=settings.HEADERS)
                        result_data = result_response.json()

                        if result_data["status"]["id"] in [1, 2]:
                            time.sleep(1)
                            continue

                        stdout = result_data.get("stdout", "")
                        stderr = result_data.get("stderr", "")
                        compile_output = result_data.get("compile_output", "")
                        message = result_data.get("message", "")
                        status_description = result_data["status"]["description"]

                        exec_time = result_data.get("time", "0")

                        if a_type == "quiz":
                            instruction = activity.description
                            examples = get_activity_examples(activity)
                            criterias = get_activity_criterias(activity)

                            ai_feedback = evaluate_student_code_with_openai(
                                code=code,
                                instruction=instruction,
                                examples=examples,
                                criterias=criterias,
                                max_score=activity.max_score,
                            )

                            score_match = re.search(r"Grading:\s*(\d+)", ai_feedback)
                            score = int(score_match.group(1)) if score_match else 0

                            sections = re.split(r'\*?\s*(?:Grading|Insight):\s*\*?\s*', ai_feedback)
                            
                            if len(sections) > 1:
                                feedback_section = sections[-1].strip()
                            else:
                                feedback_section = re.sub(r'.*Grading:\s*\d+\s*', '', ai_feedback).strip()
                            
                            feedback_section = re.sub(r'\*\*', '', feedback_section).strip()

                            if submission.score is None or score > submission.score:
                                submission.score = score
                                submission.feedback = feedback_section
                                submission.save()

                            output = f"""
                            <div class="max-w-3xl mx-auto">
                              <div class="bg-white border border-gray-200 rounded-lg shadow overflow-hidden">
                                <div class="p-4">
                                  <div class="flex items-center justify-between mb-3">
                                    <h3 class="text-sm font-semibold">🏆 Quiz Result</h3>
                                    <div class="text-sm text-gray-700">Score: <span class="font-medium">{score}</span></div>
                                  </div>
                                  <div class="bg-gray-800 text-gray-100 rounded-md p-3">
                                    <h4 class="text-xs text-gray-300">📄 Program Output</h4>
                                    <pre id="quiz-output-pre" class="mt-2 whitespace-pre-wrap text-sm bg-gray-900 text-green-300 rounded p-3 max-h-48 overflow-auto">{stdout or stderr or compile_output or message or status_description}</pre>
                                    <div class="mt-2 text-xs text-gray-400">⏱️ Run Time: <span class="font-medium">{exec_time}</span></div>
                                  </div>
                                  <div class="mt-3 bg-gradient-to-br from-white to-gray-50 border border-gray-100 rounded-md p-3">
                                    <h4 class="text-sm font-semibold">🤖 AI Feedback</h4>
                                    <div class="mt-2 text-sm text-gray-700 leading-relaxed" id="quiz-ai-feedback">{feedback_section.replace('-', '<br>')}</div>
                                  </div>
                                  <div class="mt-3 flex gap-2">
                                    <button data-copy-target="quiz-output-pre" class="copy-btn inline-flex items-center gap-2 px-3 py-1 text-xs bg-gray-700 hover:bg-gray-600 rounded text-white">Copy Output</button>
                                    <button id="copy-quiz-feedback" class="inline-flex items-center px-3 py-1 text-xs bg-black text-white rounded">Copy Feedback</button>
                                  </div>
                                </div>
                              </div>

                              <style>
                                #quiz-output-pre {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, "Roboto Mono", monospace; }}
                                .copy-btn {{ cursor: pointer; }}
                              </style>

                             <script>
                                (function(){{
                                  function copyTextFromSelector(selector){{
                                    const el = document.getElementById(selector);
                                    if(!el) return;
                                    const text = el.innerText || el.textContent || '';
                                    navigator.clipboard?.writeText(text).then(()=>{{
                                      const btn = document.querySelector('[data-copy-target="' + selector + '"]');
                                      if(btn){{ btn.textContent = 'Copied'; setTimeout(()=> btn.textContent = 'Copy Output', 1200); }}
                                    }}).catch(()=>{{}});
                                  }}

                                  document.querySelectorAll('.copy-btn').forEach(btn=>{{
                                    btn.addEventListener('click', function(e){{
                                      const target = this.getAttribute('data-copy-target');
                                      copyTextFromSelector(target);
                                    }});
                                  }});

                                  const fbBtn = document.getElementById('copy-quiz-feedback');
                                 if(fbBtn){{
                                    fbBtn.addEventListener('click', function(){{
                                      const content = document.getElementById('quiz-ai-feedback');
                                      const text = content ? content.innerText || content.textContent : '';
                                      navigator.clipboard?.writeText(text).then(()=>{{
                                        fbBtn.textContent = 'Copied'; setTimeout(()=> fbBtn.textContent = 'Copy Feedback', 1200);
                                      }}).catch(()=>{{}});
                                    }});
                                  }}
                                }})();
                              </script>
                            </div>
                            """
                        else:
                            ai_feedback = evaluate_student_code_with_openai_for_playground(code=code)

                            output = f"""
                            <div class="max-w-5xl mx-auto p-4">
                              <div class="bg-white border border-gray-200 rounded-lg shadow-lg overflow-hidden">
                                <div class="p-4 md:p-6">
                                  <div class="flex flex-col gap-4">
                                    <div class="w-full">
                                      <div class="bg-gray-800 text-gray-100 rounded-md p-3">
                                        <div class="flex items-center justify-between">
                                          <h3 class="text-sm font-semibold">📄 Program Output</h3>
                                          <div class="flex items-center gap-2">
                                            <button data-copy-target="output-pre" class="copy-btn inline-flex items-center gap-2 px-3 py-1 text-xs bg-gray-700 hover:bg-gray-600 rounded text-white">Copy</button>
                                          </div>
                                        </div>
                                        <pre id="output-pre" class="mt-3 whitespace-pre-wrap text-sm bg-gray-900 text-green-300 rounded p-3 max-h-64 overflow-auto">{stdout or stderr or compile_output or message or status_description}</pre>
                                      </div>

                                      <div class="mt-3 flex items-center justify-between text-sm text-gray-600">
                                        <div>⏱️ <span class="font-medium">Run Time:</span> <span class="ml-1">{exec_time}</span></div>
                                        <div class="text-right">Status: <span class="font-medium">{status_description}</span></div>
                                      </div>
                                    </div>

                                    <div class="w-full">
                                      <div class="h-full bg-gradient-to-br from-white to-gray-50 border border-gray-100 rounded-md p-3">
                                        <h3 class="text-sm font-semibold">🤖 AI Feedback</h3>
                                        <div class="mt-2 text-sm text-gray-700 space-y-2 leading-relaxed" id="ai-feedback">{ai_feedback.replace('-', '<br>')}</div>
                                        <div class="mt-3">
                                          <button id="copy-feedback" class="w-full inline-flex justify-center items-center gap-2 px-3 py-2 bg-black text-white rounded-md text-sm">Copy Feedback</button>
                                        </div>
                                      </div>
                                    </div>
                                  </div>
                                </div>
                              </div>

                              <style>
                                /* small helpers to ensure nice scrollbars and wrapping */
                                #output-pre {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, "Roboto Mono", monospace; }}
                                .copy-btn {{ cursor: pointer; }}
                              </style>

                              <script>
                                (function(){{
                                  function copyTextFromSelector(selector){{
                                    const el = document.getElementById(selector);
                                    if(!el) return;
                                    const text = el.innerText || el.textContent || '';
                                    navigator.clipboard?.writeText(text).then(()=>{{
                                      // flash a tiny toast
                                      const btn = document.querySelector('[data-copy-target="' + selector + '"]');
                                      if(btn){{ btn.textContent = 'Copied'; setTimeout(()=> btn.textContent = 'Copy', 1200); }}
                                    }}).catch(()=>{{}});
                                  }}

                                  document.querySelectorAll('.copy-btn').forEach(btn=>{{
                                    btn.addEventListener('click', function(e){{
                                      const target = this.getAttribute('data-copy-target');
                                      copyTextFromSelector(target);
                                    }});
                                  }});

                                  const fbBtn = document.getElementById('copy-feedback');
                                  if(fbBtn){{
                                    fbBtn.addEventListener('click', function(){{
                                      const content = document.getElementById('ai-feedback');
                                      const text = content ? content.innerText || content.textContent : '';
                                      navigator.clipboard?.writeText(text).then(()=>{{
                                        fbBtn.textContent = 'Copied'; setTimeout(()=> fbBtn.textContent = 'Copy Feedback', 1200);
                                      }}).catch(()=>{{}});
                                    }});
                                  }}
                                }})();
                              </script>
                            </div>
                            """

                        return HttpResponse(output, content_type="text/html")

                    return HttpResponse("Timeout retrieving result", status=500)

                except requests.RequestException as e:
                    return HttpResponse(f"Judge0 server error: {str(e)}", status=500)
            case _:
                return HttpResponse("Invalid action", status=400)