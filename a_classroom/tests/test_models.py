from django.test import TestCase, Client
from django.contrib.auth.models import User
from a_classroom.models import Section, Subject
from b_enrollment.models import StudentSubject
from c_activities.models import Activity, ActivitySubmission, ActivityExample
from django.conf import settings
import json

class TestModels(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username = "testusername",
            first_name = "testfirst_name",
            last_name = "testlast_name",
            email = "testemail@gmail.com",
            password = "testpass"
        )
        self.section = Section.objects.create(
            name = "test section"
        )
        self.subject = Subject.objects.create(
            instructor = self.user,
            subject_id = "subj12",
            name = "test subject",
            section = self.section,
            course_code = "7tsub1"
        )
        self.student_subject = StudentSubject.objects.create(
            student = self.user,
            subject = self.subject
        )
        self.client = Client()

    
    def test_userprofile_model_using_email_without_numbers(self):
        user_profile = self.user.userprofile

        self.assertEqual(user_profile.user.username, "testusername")
        self.assertEqual(user_profile.user.first_name, "testfirst_name")
        self.assertEqual(user_profile.user.last_name, "testlast_name")
        self.assertEqual(user_profile.user.email, "testemail@gmail.com")
        self.assertEqual(user_profile.role, "Instructor")
        self.assertEqual(str(user_profile), "testusername Profile Photo")
        default_image_url = f'{settings.MEDIA_URL}{user_profile.image}'
        self.assertEqual(user_profile.get_image_url(), default_image_url)

    def test_activity_model(self):
        activity = Activity.objects.create(
            subject = self.subject,
            activity_id = "act123",
            title = "activity 1",
            description = "create a list of fruits and loop through it using a for loop in python",
            max_score = 100,
            due_at = "2025-05-30 11:59",
            is_archived = False
        )

        submission = ActivitySubmission.objects.create(
            student = self.user,
            activity = activity,
            submitted_code = "fruits = ['mango', 'apple', 'banana', 'pineapple'] for fruit in fruits:\n     print(fruit)",
            feedback = "Good Code",
            score = 100
        )

        def create_activity():
            example = []
            for i in range(5):
                act = f"activity {i}"
            
                example.append(act)

            return example

        example = create_activity()
        example_str = json.dumps(example)
        act_example = ActivityExample.objects.create(
            activity = activity,
            example_text = example_str
        )

        self.assertEqual(submission.student, self.user)
        self.assertEqual(submission.activity, activity)
        self.assertEqual(submission.feedback, "Good Code")
        self.assertEqual(submission.score, 100)
        self.assertEqual(act_example.activity, activity)
        print(f"{act_example.activity} is equal to {activity}")