from django import forms
from django.contrib.auth.forms import UserCreationForm
from accounts.models import User
import re

class SingupForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")
        

    def __init__(self, *args, **kwargs):
        super(SingupForm, self).__init__(*args, **kwargs)
        del self.fields['email']

    def save(self, commit=True):
        new_user = self.instance.email
        if re.match(r'^[(a-z0-9\_\-\.)]+@[(a-z0-9\_\-\.)]+\.[(a-z)]{2,15}$', new_user.lower()):
            self.instance.email = self.instance.email
        else:
            self.instance.email = None
        return super(SingupForm, self).save(commit=commit)