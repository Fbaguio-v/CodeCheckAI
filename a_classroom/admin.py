from django.contrib import admin
from .models import Section, Subject

# Register your models here.
class SectionAdmin(admin.ModelAdmin):
    list_display = ('name', )

class SubjectAdmin(admin.ModelAdmin):
    list_display = ('instructor', 'subject_id', 'name', 'section', 'course_code', 'is_archived')


admin.site.register(Section, SectionAdmin)
admin.site.register(Subject, SubjectAdmin)