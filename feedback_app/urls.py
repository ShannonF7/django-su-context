from django.urls import path
from . import views

app_name = "feedback"
urlpatterns = [
    path("records/", views.record_list, name="record_list"),
    path("records/<int:id>/", views.record_detail, name="record_detail"),
    path("feedback/edit/<int:feedback_id>/", views.edit_feedback, name="edit_feedback"),
    path(
        "feedback/update_reference/<int:feedback_id>/",
        views.update_reference,
        name="update_reference",
    ),
    path("upload_page/<int:feedback_id>/", views.upload_page, name="upload_page"),
    path("add_document/", views.add_document, name="add_document"),
    path("delete_document/", views.delete_document, name="delete_document"),
    path("check_task_status/", views.check_task_status, name="check_task_status"),
    path("upload_history/", views.upload_history, name="upload_history"),
    path("retry_document/", views.retry_document_upload_view, name="retry_document"),
]
