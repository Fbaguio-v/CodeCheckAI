from django.contrib.auth.forms import UserCreationForm
from django import forms
from django.contrib.auth.models import User
import uuid

class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            "autocomplete": "email",
            "placeholder": "Email Address..."
        })
    )
    
    agree_terms = forms.BooleanField(
        required=True,
        error_messages={'required': 'You must agree to the Terms and Conditions and Privacy Policy'},
        widget=forms.CheckboxInput(attrs={'class': 'mr-2'})
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "password1", "password2", "agree_terms"]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].widget.attrs.update({
            "placeholder": "Password"
        })
        self.fields["password2"].widget.attrs.update({
            "placeholder": "Confirm Password"
        })
        self.fields["first_name"].widget.attrs.update({"placeholder": "First Name"})
        self.fields["last_name"].widget.attrs.update({"placeholder": "Last Name"})

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Email is already in use.")
        return email
    
    def save(self, commit=True):
        user = super().save(commit=False)
        
        user.first_name = self.cleaned_data['first_name'].capitalize()
        user.last_name = self.cleaned_data['last_name'].capitalize()
        
        user.username = self.cleaned_data['email'].split('@')[0] + uuid.uuid4().hex[:6]
        
        if commit:
            user.save()
        return user

class CustomLoginForm(forms.Form):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            "autocomplete": "email",
            "placeholder": "Email Address..."
        })
    )
    password = forms.CharField(widget=forms.PasswordInput(attrs={"placeholder": "Password"}))