from django.contrib import admin
from .models import UserProfile, StudentSubject
# Register your models here.
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'image')

class StudentSubjectAdmin(admin.ModelAdmin):
    list_display = ('get_student', 'get_subject', 'joined_at')

    def get_student(self, obj):
        return obj.student.username
    
    get_student.admin_order_field = 'student'
    get_student.short_description = 'Student'

    def get_subject(self, obj):
        return obj.subject.name

    get_subject.admin_order_field = 'subject'
    get_subject.short_description = 'Subject'

admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(StudentSubject, StudentSubjectAdmin)