from django import forms

class CreateActivityForm(forms.Form):
	title = forms.CharField(label = "Activity title", max_length = 255)
	description = forms.CharField(
        label="Activity Description",
        widget=forms.Textarea
    	)
	max_score = forms.IntegerField(
        label="Maximum Score",
        min_value=0,
        initial=100
    	)
	due_at = forms.DateTimeField(label = 'Due Date', widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}), required = False)