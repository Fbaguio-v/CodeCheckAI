from django.db import models
from django.contrib.auth.models import User
from a_classroom.models import Subject
import random
import string

class Activity(models.Model):
    ACTIVITY_TYPES = [
        ('activity', 'Activity'),
        ('quiz', 'Quiz')
    ]
    
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='activities')
    activity_id = models.CharField(max_length=8, unique=True, editable=False)
    type = models.CharField(max_length=10, choices=ACTIVITY_TYPES, default='activity')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    max_score = models.PositiveIntegerField(default=100)
    max_attempt = models.PositiveIntegerField(null=True, blank=True, default=3)
    created_at = models.DateTimeField(auto_now_add=True)
    due_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.activity_id:
            self.activity_id = self.generate_unique_activity_id()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_unique_activity_id():
        characters = string.ascii_uppercase + string.digits
        while True:
            unique_id = ''.join(random.choices(characters, k=8))
            if not Activity.objects.filter(activity_id=unique_id).exists():
                return unique_id

class ActivitySubmission(models.Model):
    STATUS_CHOICES = [
        ('submitted', 'Submitted'),
        ('returned', 'Returned'),
        ('in_progress', 'In Progress')  # for quiz-like behavior
    ]
    
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activity_submissions')
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name='submissions')
    submitted_code = models.TextField(default="", null=True, blank=True)
    saved_code = models.TextField(default="", null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    feedback = models.TextField(default="", null=True, blank=True)
    score = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, default=None)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='in_progress')
    attempt = models.PositiveIntegerField(null=True, blank=True)  # only for quizzes
    evaluator = models.CharField(max_length=10, null=True, blank=True)

class ActivityExample(models.Model):
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name='examples')
    example_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

class ActivityCriteria(models.Model):
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name='criteria')
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)