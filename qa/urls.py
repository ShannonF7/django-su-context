from django.urls import path
from . import views

app_name = "qa"
urlpatterns = [
    path("", views.qa_page, name="qa_page"),
    path("ask/", views.ask_question, name="ask_question"),
    path("router/", views.route_page, name="route_page"),
    path(
        "submit_feedback/<int:record_id>/",
        views.submit_feedback,
        name="submit_feedback",
    ),
    path("images/<str:image_name>", views.proxy_image, name="proxy_image"),
]
