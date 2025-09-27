from django import forms
from .models import UserProfile
from a_classroom.models import Subject

class UploadImageForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['image']
        widgets = {
            'image': forms.ClearableFileInput(attrs={'class': 'border border-solid border-gray-300'})
        }

class JoinClassForm(forms.Form):
    subject_id = forms.CharField(label='Join Class')

    def clean_subject_id(self):
        subject_id = self.cleaned_data.get('subject_id')
        try:
            subject = Subject.objects.get(subject_id = subject_id)
        except Subject.DoesNotExist:
            raise forms.ValidationError("Invalid Subject ID. Please try again.")
        return subject