from django import forms
from feedback_app.models import ChangeLog, Feedback


class ChangelogForm(forms.ModelForm):
    feedback_state = forms.ChoiceField(
        choices=Feedback.STATE_CHOICES, required=False, label="Feedback 状态"
    )

    class Meta:
        model = ChangeLog
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.feedback:
            self.fields["feedback_state"].initial = self.instance.feedback.state

    def save(self, commit=True):
        instance = super().save(commit=False)
        new_state = self.cleaned_data.get("feedback_state")
        if (
            new_state is not None
            and instance.feedback
            and instance.feedback.state != int(new_state)
        ):
            instance.feedback.state = new_state
            instance.feedback.save()
        if commit:
            instance.save()
        return instance
