from django.contrib import admin
from .models import Activity, ActivitySubmission, ActivityExample, ActivityCriteria
# Register your models here.

class ActivityAdmin(admin.ModelAdmin):
    list_display = ('get_subject', 'activity_id', 'title', 'description', 'max_score', 'created_at', 'due_at', 'updated_at')

    def get_subject(self, obj):
        return obj.subject.name

    get_subject.short_description = "Subject"

class ActivitySubmissionAdmin(admin.ModelAdmin):
    list_display = ('get_student', 'get_activity', 'submitted_code', 'submitted_at', 'feedback', 'score', 'saved_code', 'status', 'evaluator')

    def get_student(self, obj):
        return obj.student.username
    get_student.admin_order_field = 'student'
    get_student.short_description = 'Student'

    def get_activity(self, obj):
        return obj.activity.title
    get_activity.admin_order_field = 'activity'
    get_activity.short_description = 'Activity'

class ActivityExampleAdmin(admin.ModelAdmin):
    list_display = ('activity', 'example_text', 'created_at')

class ActivityCriteriaAdmin(admin.ModelAdmin):
    list_display = ('activity', 'text', 'created_at')

admin.site.register(Activity, ActivityAdmin)
admin.site.register(ActivitySubmission, ActivitySubmissionAdmin)
admin.site.register(ActivityExample, ActivityExampleAdmin)
admin.site.register(ActivityCriteria, ActivityCriteriaAdmin)