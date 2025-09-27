from django import forms

class CreateSubjectForm(forms.Form):
    course_code = forms.CharField(label = "Course Code", max_length = 100)
    section_name = forms.CharField(label = "Section", max_length = 100)
    name = forms.CharField(label = "Subject", max_length = 200)