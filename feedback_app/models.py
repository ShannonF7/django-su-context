from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from accounts.models import CustomUser
from django.utils.timezone import is_aware, timezone


class Record(models.Model):
    record_uuid = models.CharField(max_length=32, unique=True, editable=False)
    username = models.CharField(max_length=50)
    question = models.CharField(max_length=100)
    answer = models.TextField()
    create_time = models.DateTimeField(auto_now_add=True)

    @property
    def raw_create_time(self):
        value = self.create_time
        if is_aware(value):
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    class Meta:
        # managed = False
        db_table = "record"
        ordering = ["-create_time"]

    def __str__(self):
        return f"{self.question[:20]} - {self.username}"


class Feedback(models.Model):
    STATE_CHOICES = [
        (1, "Thumb Up"),
        (0, "Thumb Down"),
    ]

    record = models.ForeignKey(
        Record,
        on_delete=models.CASCADE,
        related_name="feedbacks",
        null=True,
        blank=True,
    )
    username = models.CharField(max_length=50)
    state = models.SmallIntegerField(choices=STATE_CHOICES, null=True, blank=True)
    feedback_answer = models.CharField(max_length=50, default="none")
    create_time = models.DateTimeField(auto_now_add=True)

    @property
    def raw_create_time(self):
        value = self.create_time
        if is_aware(value):
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    class Meta:
        # managed = False
        db_table = "feedback"
        ordering = ["-create_time"]
        indexes = [
            models.Index(fields=["record", "username"]),
        ]

    def __str__(self):
        return f"Feedback for Record {self.record.id}"


class ChangeLog(models.Model):
    feedback = models.ForeignKey(
        Feedback, on_delete=models.CASCADE, default=1, related_name="changelogs"
    )
    document_id = models.CharField(max_length=255, default="default_document_id")
    original = models.TextField()
    modified = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    modified_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="changelogs",
    )
    score = models.IntegerField(null=True, blank=True, verbose_name="评分")
    comments = models.TextField(null=True, blank=True, verbose_name="评语")
    state = models.IntegerField(default=0)

    class Meta:
        ordering = ["-timestamp"]
        managed = True

    def __str__(self):
        return f"Change at {self.timestamp} by {self.modified_by}"


class DocumentTask(models.Model):
    TASK_TYPES = [
        ("add", "添加文档"),
        ("delete", "删除文档"),
    ]

    STATUS_CHOICES = [
        ("pending", "处理中"),
        ("success", "成功"),
        ("failed", "失败"),
    ]

    task_type = models.CharField(max_length=20, choices=TASK_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    document_id = models.CharField(max_length=100, blank=True, null=True)
    content = models.TextField(blank=True, null=True)
    keywords = models.TextField(blank=True, null=True)
    message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, verbose_name="是否活跃")

    uploaded_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_tasks",
        verbose_name="上传者",
    )
    score = models.IntegerField(null=True, blank=True, verbose_name="评分")
    comments = models.TextField(null=True, blank=True, verbose_name="评语")
    state = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.get_task_type_display()} - {self.get_status_display()}"

    def mark_as_deleted(self):
        """Mark the task as deleted."""
        self.is_active = False
        self.save()
