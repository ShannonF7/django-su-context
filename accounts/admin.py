from django.contrib import admin
from feedback_app.models import ChangeLog, Feedback, Record
from accounts.models import CustomUser
from django.utils.translation import gettext_lazy as _
from django.contrib.admin import SimpleListFilter
from datetime import date, timedelta
from django import forms
from django.contrib.auth.admin import UserAdmin


class ChangeLogAdminForm(forms.ModelForm):
    feedback_state = forms.ChoiceField(
        label="Feedback 状态",
        choices=Feedback.STATE_CHOICES,
        required=False,
    )

    class Meta:
        model = ChangeLog
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.feedback_id:
            feedback = Feedback.objects.filter(id=self.instance.feedback_id).first()
            if feedback:
                self.fields["feedback_state"].initial = feedback.state

    def save(self, commit=True):
        instance = super().save(commit)
        feedback = Feedback.objects.filter(id=instance.feedback_id).first()
        if feedback:
            feedback.state = self.cleaned_data.get("feedback_state")
            feedback.save()
        return instance


class DateRangeFilter(SimpleListFilter):
    title = _("Date range")
    parameter_name = "date_range"

    def lookups(self, request, model_admin):
        return (
            ("today", _("Today")),
            ("this_week", _("This week")),
            ("this_month", _("This month")),
        )

    def queryset(self, request, queryset):
        today = date.today()
        if self.value() == "today":
            return queryset.filter(timestamp__date=today)
        elif self.value() == "this_week":
            start_date = today - timedelta(days=today.weekday())
            end_date = start_date + timedelta(days=6)
            return queryset.filter(timestamp__date__range=(start_date, end_date))
        elif self.value() == "this_month":
            start_date = date(today.year, today.month, 1)
            next_month = today.replace(day=28) + timedelta(days=4)
            end_date = next_month - timedelta(days=next_month.day)
            return queryset.filter(timestamp__date__range=(start_date, end_date))
        return queryset


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ("username", "phone", "is_active", "is_staff")
    search_fields = ("username", "phone")
    ordering = ("username",)

    readonly_fields = ("date_joined",)

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (_("Personal info"), {"fields": ("phone",)}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (_("Important dates"), {"fields": ("last_login",)}),  # ✅ 去掉 date_joined
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "phone", "password1", "password2"),
            },
        ),
    )

    class Media:
        css = {"all": ("css/admin_fix.css",)}


@admin.register(ChangeLog)
class ChangelogAdmin(admin.ModelAdmin):
    form = ChangeLogAdminForm

    list_display = (
        "id",
        "feedback_id",
        "document_id",
        "timestamp",
        "modified_by",
        "original_excerpt",
        "modified_excerpt",
        "feedback_state_display",
        "record_question",
        "record_answer_excerpt",
    )
    list_display_links = ("id",)
    search_fields = (
        "feedback_id",
        "original",
        "modified",
    )
    list_filter = ("timestamp", "modified_by", DateRangeFilter)

    readonly_fields = (
        "timestamp",
        "document_id",
        "original",
        "modified",
        "full_record_question",
        "full_record_answer",
    )

    def has_add_permission(self, request):
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        # 缓存 Feedback 和 Record
        self._feedback_map = {fb.id: fb for fb in Feedback.objects.all()}
        record_ids = {
            fb.record_id for fb in self._feedback_map.values() if fb.record_id
        }
        self._record_map = {
            rec.id: rec for rec in Record.objects.filter(id__in=record_ids)
        }

        return qs

    def original_excerpt(self, obj):
        return (
            (obj.original[:50] + "...")
            if obj.original and len(obj.original) > 50
            else obj.original
        )

    original_excerpt.short_description = "原始内容"

    def modified_excerpt(self, obj):
        return (
            (obj.modified[:50] + "...")
            if obj.modified and len(obj.modified) > 50
            else obj.modified
        )

    modified_excerpt.short_description = "修改后内容"

    def _get_feedback(self, obj):
        # 优先用缓存，没有再查数据库（防止详情页调用时缓存未生成）
        feedback = getattr(self, "_feedback_map", {}).get(obj.feedback_id)
        if not feedback:
            feedback = Feedback.objects.filter(id=obj.feedback_id).first()
        return feedback

    def _get_record(self, feedback):
        if not feedback or not feedback.record_id:
            return None
        # 优先用缓存，没有再查数据库
        record = getattr(self, "_record_map", {}).get(feedback.record_id)
        if not record:
            record = Record.objects.filter(id=feedback.record_id).first()
        return record

    def record_question(self, obj):
        feedback = self._get_feedback(obj)
        record = self._get_record(feedback)
        return record.question if record else "(记录缺失)"

    record_question.short_description = "问题"

    def record_answer_excerpt(self, obj):
        feedback = self._get_feedback(obj)
        record = self._get_record(feedback)
        if record and record.answer:
            return (
                record.answer[:50] + "..." if len(record.answer) > 50 else record.answer
            )
        return "(记录缺失)"

    record_answer_excerpt.short_description = "回答内容"

    def full_record_question(self, obj):
        feedback = self._get_feedback(obj)
        record = self._get_record(feedback)
        return record.question if record else "(记录缺失)"

    full_record_question.short_description = "完整问题"

    def full_record_answer(self, obj):
        feedback = self._get_feedback(obj)
        record = self._get_record(feedback)
        return record.answer if record else "(记录缺失)"

    full_record_answer.short_description = "完整回答"

    def feedback_state_display(self, obj):
        feedback = self._get_feedback(obj)
        if feedback:
            return dict(Feedback.STATE_CHOICES).get(feedback.state, "Unknown")
        else:
            return "(无反馈)"

    feedback_state_display.short_description = "反馈状态"

    class Media:
        css = {"all": ("admin/custom.css",)}