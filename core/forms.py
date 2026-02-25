# social/forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from .models import Profile, Activity

User = get_user_model()


class UserRegistrationForm(UserCreationForm):
    """
    User registration form with email validation.
    Inherits from UserCreationForm for password validation.
    """
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"class": "form-control"}),
        help_text="Enter a valid email address.",
    )

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "password1": forms.PasswordInput(attrs={"class": "form-control"}),
            "password2": forms.PasswordInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].help_text = (
            "Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only."
        )
        self.fields["password1"].help_text = (
            "Your password must contain at least 8 characters and cannot be entirely numeric."
        )

    def clean_email(self):
        """
        Validate that the email is unique and properly formatted.
        """
        email = self.cleaned_data.get("email")
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("A user with this email already exists.")
        return email

    def save(self, commit=True):
        """
        Save the user with the validated email.
        """
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    """
    Clean and simple login form.
    """
    username = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control", "autofocus": True})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control"})
    )

    class Meta:
        model = User
        fields = ("username", "password")

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.fields["username"].label = "Username or Email"


class ProfileUpdateForm(forms.ModelForm):
    """
    Form for updating user profile information.
    """
    class Meta:
        model = Profile
        fields = ("bio", "age", "gender", "city", "interests")
        widgets = {
            "bio": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Tell us about yourself...",
                }
            ),
            "age": forms.NumberInput(attrs={"class": "form-control"}),
            "gender": forms.Select(attrs={"class": "form-control"}),
            "city": forms.TextInput(attrs={"class": "form-control"}),
            "interests": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "List your interests separated by commas...",
                }
            ),
        }

    def clean_age(self):
        """
        Validate that age is a reasonable value.
        """
        age = self.cleaned_data.get("age")
        if age is not None and (age < 13 or age > 120):
            raise ValidationError("Please enter a valid age between 13 and 120.")
        return age


class ActivityForm(forms.ModelForm):
    """
    Form for creating and updating activities.
    """
    class Meta:
        model = Activity
        fields = ("title", "description", "location", "city", "date", "time")
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Activity title"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Describe the activity...",
                }
            ),
            "location": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Full address or landmark"}
            ),
            "city": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "City name"}
            ),
            "date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "time": forms.TimeInput(
                attrs={"class": "form-control", "type": "time"}
            ),
        }

    def clean_date(self):
        """
        Ensure the activity date is not in the past.
        """
        from django.utils import timezone
        date = self.cleaned_data.get("date")
        if date and date < timezone.now().date():
            raise ValidationError("Activity date cannot be in the past.")
        return date