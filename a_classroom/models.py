from django.db import models
from django.contrib.auth.models import User
import random
import string

class Section(models.Model):
    name = models.CharField(max_length=100, unique=True)
    students = models.ManyToManyField(User, related_name="sections", blank=True)

class Subject(models.Model):
    instructor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subjects')
    subject_id = models.CharField(max_length=8, unique=True, editable=False)
    name = models.CharField(max_length=200)
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='subjects')
    course_code = models.TextField(blank=True)
    students = models.ManyToManyField(User, related_name='joined_subjects', blank=True, through='b_enrollment.StudentSubject')
    is_archived = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.subject_id:
            self.subject_id = self.generate_unique_subject_id()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_unique_subject_id():
        characters = string.ascii_uppercase + string.digits
        while True:
            unique_id = ''.join(random.choices(characters, k=8))
            if not Subject.objects.filter(subject_id=unique_id).exists():
                return unique_id
