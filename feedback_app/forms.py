from django import forms
from .models import Feedback


class FeedbackEditForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ['state', 'feedback_answer']
        widgets = {
            'state': forms.Select(choices=[
                (None, '-- 请选择评分 --'),
                (1, '👍 好评'),
                (0, '👎 差评')
            ], attrs={'class': 'form-select'}),
            'feedback_answer': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': '请输入详细反馈内容'
            })
        }