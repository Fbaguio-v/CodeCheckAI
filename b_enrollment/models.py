from django.db import models
from django.contrib.auth.models import User
from django.conf import settings

# Create your models here.
class Role(models.TextChoices):
    ADMIN = 'Admin', 'Admin'
    INSTRUCTOR = 'Instructor', 'Instructor'
    STUDENT = 'Student', 'Student'

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete = models.CASCADE)
    role = models.CharField(max_length = 20, choices = Role.choices, default = Role.STUDENT)
    image = models.ImageField(upload_to='mysite_images/', null=True, blank=True, default='mysite_images/default.jpg')

    def __str__(self):
        return f'{self.user.username} Profile Photo'

    def get_image_url(self):
        if self.image:
            return f'{settings.MEDIA_URL}{self.image}'
        return f'{settings.STATIC_URL}images/default.jpg'

class StudentSubject(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='student_subjects')
    subject = models.ForeignKey('a_classroom.Subject', on_delete=models.CASCADE, related_name='student_subjects')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'subject')