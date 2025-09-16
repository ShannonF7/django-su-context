from django.urls import path
from . import views
app_name = "adminpanel"

urlpatterns = [
    path("dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("users/", views.user_list, name="user_list"),
    path("users/add/", views.user_detail, name="user_add"),
    path("users/<int:user_id>/", views.user_detail, name="user_detail"),
    path("users/<int:user_id>/delete/", views.user_delete, name="user_delete"),
    path("logs/", views.changelog_list, name="changelog_list"),
    path("user-behavior/", views.user_list_view, name="user_behavior_overview"),
    path(
        "user-behavior/<int:user_id>/",
        views.user_behavior_overview,
        name="user_behavior_detail",
    ),
    path(
        "quick-evaluate/<str:activity_type>/<int:activity_id>/",
        views.quick_evaluate_activity,
        name="quick_evaluate_activity",
    ),
    path("upload-detail/<int:upload_id>/", views.upload_detail, name="upload_detail"),
    # path('performance/', views.employee_performance, name='employee_performance'),
    # path('performance/export/', views.export_performance_report, name='export_performance_report'),
    path("performance/dashboard/", views.employee_performance_dashboard, name="employee_performance_dashboard",),
    path("performance/employee/<int:employee_id>/", views.get_employee_detail, name="get_employee_detail",),
    path("performance/export/", views.export_performance_report, name="export_performance_report",),
]
