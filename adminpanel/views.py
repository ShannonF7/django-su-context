from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth import get_user_model
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from .forms import UserForm
from django.contrib import messages
from django.core.paginator import Paginator
from feedback_app.models import ChangeLog, Feedback, Record, DocumentTask
from accounts.models import CustomUser
from django.views.decorators.http import require_POST

from django.db.models import Q, Sum, Count, Avg, Sum, F
from django.utils import timezone
from datetime import datetime, timedelta
import json
from difflib import ndiff, HtmlDiff
from django.utils.html import format_html, escape
from django.utils.safestring import mark_safe
from django.core.exceptions import ObjectDoesNotExist
import re
import difflib
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.decorators import user_passes_test
import csv
from django.contrib.admin.views.decorators import staff_member_required
from django.core.serializers.json import DjangoJSONEncoder
from io import StringIO


User = get_user_model()


def superuser_required(view_func):
    return user_passes_test(lambda u: u.is_superuser)(view_func)


@superuser_required
def admin_dashboard(request):
    return render(request, "adminpanel/dashboard_simple.html")


@superuser_required
def user_list(request):
    users_list = User.objects.all().order_by("-id")
    paginator = Paginator(users_list, 10)
    page_number = request.GET.get("page")
    users = paginator.get_page(page_number)
    return render(request, "adminpanel/user_list.html", {"users": users})


@superuser_required
def user_detail(request, user_id=None):
    if user_id:
        user = get_object_or_404(User, pk=user_id)
    else:
        user = None

    if request.method == "POST":
        form = UserForm(request.POST, instance=user)
        if form.is_valid():
            new_user = form.save(commit=False)
            password = form.cleaned_data.get("password")
            if password and password.strip():
                new_user.set_password(password)
            else:
                pass

            new_user.save()

            if user:
                messages.success(request, "用户信息已更新。")
            else:
                messages.success(request, "新用户已添加。")
            return redirect("adminpanel:user_list")
    else:
        form = UserForm(instance=user)

    return render(
        request,
        "adminpanel/user_detail.html",
        {
            "form": form,
            "user": user,
            "is_edit": bool(user),
        },
    )


@superuser_required
def user_delete(request, user_id):
    user = get_object_or_404(User, pk=user_id)

    if user == request.user:
        messages.error(request, "你不能删除自己！")
        return redirect("adminpanel:user_list")

    if request.method == "POST":
        user.delete()
        messages.success(request, f"用户 {user.username} 已成功删除。")
        return redirect("adminpanel:user_list")

    return render(request, "adminpanel/user_confirm_delete.html", {"user": user})


@superuser_required
def changelog_list(request):
    changelogs = (
        ChangeLog.objects.select_related("modified_by", "feedback__record")
        .values(
            "id",
            "original",
            "modified",
            "timestamp",
            "feedback__id",
            "feedback__record__question",
            "feedback__record__answer",
            "feedback__state",
            "modified_by__username",
            "document_id",
        )
        .order_by("-timestamp")
    )

    paginator = Paginator(changelogs, 10)
    page_number = request.GET.get("page")
    paginated_changelogs = paginator.get_page(page_number)
    page_range = paginated_changelogs.paginator.get_elided_page_range(
        number=paginated_changelogs.number,
        on_each_side=2,
        on_ends=1,
    )

    context = {
        "changelogs": paginated_changelogs,
        "page_range": page_range,
    }

    return render(request, "adminpanel/changelog_list.html", context)


@superuser_required
def user_list_view(request):
    query = request.GET.get("q", "")
    feedback_start_date = timezone.make_aware(datetime(2025, 3, 1))

    if query:
        users = (
            User.objects.filter(Q(is_active=True) & Q(username__icontains=query))
            .annotate(
                changelog_count=Count(
                    "changelogs",
                    filter=Q(changelogs__state=0)
                    & Q(changelogs__timestamp__gte=feedback_start_date),
                ),
                documenttask_count=Count(
                    "uploaded_tasks",
                    filter=Q(uploaded_tasks__state=0)
                    & Q(uploaded_tasks__task_type="add")
                    & Q(uploaded_tasks__status="success")
                    & Q(uploaded_tasks__is_active=True)
                    & Q(uploaded_tasks__created_at__gte=feedback_start_date),
                ),
                activity_count=F("changelog_count") + F("documenttask_count"),
            )
            .order_by("-activity_count", "-id")
        )
    else:
        users = (
            User.objects.filter(is_active=True)
            .annotate(
                changelog_count=Count(
                    "changelogs",
                    filter=Q(changelogs__state=0)
                    & Q(changelogs__timestamp__gte=feedback_start_date),
                ),
                documenttask_count=Count(
                    "uploaded_tasks",
                    filter=Q(uploaded_tasks__state=0)
                    & Q(uploaded_tasks__task_type="add")
                    & Q(uploaded_tasks__status="success")
                    & Q(uploaded_tasks__is_active=True)
                    & Q(uploaded_tasks__created_at__gte=feedback_start_date),
                ),
                activity_count=F("changelog_count") + F("documenttask_count"),
            )
            .order_by("-activity_count", "-id")
        )

    paginator = Paginator(users, 10)
    page_number = request.GET.get("page")

    try:
        page_obj = paginator.get_page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.get_page(1)
    except EmptyPage:
        page_obj = paginator.get_page(paginator.num_pages)

    return render(
        request,
        "adminpanel/user_behavior_list.html",
        {"page_obj": page_obj, "query": query},
    )


def generate_side_by_side_diff_html(text1, text2):
    matcher = difflib.SequenceMatcher(None, text1, text2)
    html_parts = [
        '<div class="simple-diff-container">',
        '<div class="diff-row">',
        '<div class="diff-label">旧</div>',
        '<div class="diff-content diff-original">',
    ]
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        text_segment = escape(text1[i1:i2])
        if tag == "equal":
            html_parts.append(text_segment)
        elif tag == "delete" or tag == "replace":
            html_parts.append(f'<del class="diff-remove">{text_segment}</del>')
    html_parts.append("</div>")
    html_parts.append("</div>")
    html_parts.append('<div class="diff-row">')
    html_parts.append('<div class="diff-label">新</div>')
    html_parts.append('<div class="diff-content diff-modified">')

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        text_segment = escape(text2[j1:j2])
        if tag == "equal":
            html_parts.append(text_segment)
        elif tag == "insert" or tag == "replace":
            html_parts.append(f'<ins class="diff-add">{text_segment}</ins>')

    html_parts.append("</div>")
    html_parts.append("</div>")
    html_parts.append("</div>")
    return mark_safe("".join(html_parts))


@superuser_required
def user_behavior_overview(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    uploads = DocumentTask.objects.filter(
        uploaded_by=user,
        task_type="add",
        is_active=True,
        state=0,
    ).order_by("-created_at")

    modifications = (
        ChangeLog.objects.filter(modified_by=user, state=0)
        .select_related("feedback", "feedback__record")
        .order_by("-timestamp")
    )
    all_activities = []

    for upload in uploads:
        content = upload.content or ""
        all_activities.append(
            {
                "type": "upload",
                "id": upload.id,
                "timestamp": upload.created_at,
                "content": content,
                "content_preview": content[:100] + "..."
                if len(content) > 100
                else content,
                "status": upload.status,
                "task_type": upload.get_task_type_display(),
                "keywords": upload.keywords or "",
                "message": f"评分: {upload.score}/100 - {upload.comments}"
                if upload.score is not None
                else "",
                "object": upload,
            }
        )

    for mod in modifications:
        original = mod.original or ""
        modified = mod.modified or ""
        question = "未知问题"
        try:
            if mod.feedback and mod.feedback.record:
                question = mod.feedback.record.question or "未知问题"
            else:
                question = "关联问题记录缺失"
        except ObjectDoesNotExist:
            question = "关联问题已被删除"
        except AttributeError:
            question = "问题信息获取失败"

        diff_html = generate_side_by_side_diff_html(original, modified)
        all_activities.append(
            {
                "type": "modification",
                "id": mod.id,
                "timestamp": mod.timestamp,
                "content": f"修改了问题：{question[:50] + '...' if len(question) > 50 else question}",
                "diff_html": diff_html,
                "message": f"评分: {mod.score}/100 - {mod.comments}"
                if mod.score is not None
                else "",
                "object": mod,
            }
        )
    all_activities.sort(key=lambda x: x["timestamp"], reverse=True)
    paginator = Paginator(all_activities, 5)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    total_uploads = uploads.count()
    successful_uploads = uploads.filter(status="success").count()

    stats = {
        "total_uploads": total_uploads,
        "successful_uploads": successful_uploads,
        "total_modifications": modifications.count(),
        "success_rate": (successful_uploads / total_uploads * 100)
        if total_uploads > 0
        else 0,
    }

    context = {
        "user": user,
        "activities": page_obj,
        "stats": stats,
    }

    return render(request, "adminpanel/user_behavior_overview.html", context)


@superuser_required
@require_POST
def quick_evaluate_activity(request, activity_type, activity_id):
    try:
        data = json.loads(request.body)
        score = data.get("score", 0)
        comments = data.get("comments", "")

        if activity_type == "upload":
            activity = DocumentTask.objects.get(id=activity_id)
            activity.score = score
            activity.comments = comments
            activity.save()

        elif activity_type == "modification":
            activity = ChangeLog.objects.get(id=activity_id)
            activity.score = score
            activity.comments = comments
            activity.save()

        else:
            return JsonResponse({"success": False, "message": "不支持的行为类型"})

        return JsonResponse({"success": True, "message": "评分已保存", "score": score})

    except DocumentTask.DoesNotExist:
        return JsonResponse({"success": False, "message": "找不到上传记录"}, status=404)

    except ChangeLog.DoesNotExist:
        return JsonResponse({"success": False, "message": "找不到修改记录"}, status=404)

    except Exception as e:
        return JsonResponse(
            {"success": False, "message": f"评分失败：{str(e)}"}, status=500
        )


@superuser_required
def upload_detail(request, upload_id):
    try:
        upload = DocumentTask.objects.get(id=upload_id)

        local_timezone = timezone.get_current_timezone()

        local_created_at = upload.created_at.astimezone(local_timezone)

        detail_data = {
            "task_type": upload.get_task_type_display(),
            "document_id": upload.document_id or "无文档ID",
            "upload_time": local_created_at.strftime("%Y-%m-%d %H:%M"),
            "status": upload.status,
            "score": upload.score if upload.score is not None else "未评分",
            "keywords": upload.keywords.split(",") if upload.keywords else [],
            "content": upload.content or "无内容",
            "message": upload.message or "无消息",
            "comments": upload.comments or "无评语",
        }

        return JsonResponse(
            {
                "success": True,
                "data": detail_data,
                "status_info": {
                    "status": upload.status,
                    "score": upload.score,
                    "comments": upload.comments,
                },
            }
        )

    except DocumentTask.DoesNotExist:
        return JsonResponse({"success": False, "message": "找不到上传记录"}, status=404)


def is_superuser(user):
    return user.is_superuser


@staff_member_required
@user_passes_test(is_superuser)
def employee_performance_dashboard(request):
    employees = CustomUser.objects.all()

    feedback_start_date = timezone.make_aware(datetime(2025, 3, 1))
    total_stats = {
        "change_count": ChangeLog.objects.filter(state=0).count(),
        "change_avg_score": round(
            ChangeLog.objects.filter(state=0).aggregate(avg=Avg("score"))["avg"] or 0, 1
        ),
        "upload_count": DocumentTask.objects.filter(
            state=0, is_active=True, task_type="add", status="success"
        ).count(),
        "upload_avg_score": round(
            DocumentTask.objects.filter(
                state=0, is_active=True, task_type="add", status="success"
            ).aggregate(avg=Avg("score"))["avg"]
            or 0,
            1,
        ),
        "feedback_count": Feedback.objects.filter(
            state=0, create_time__gte=feedback_start_date
        ).count(),
    }

    performance_data = []
    for employee in employees:
        change_logs = ChangeLog.objects.filter(modified_by=employee, state=0)
        change_count = change_logs.count()
        change_avg_score = change_logs.aggregate(avg=Avg("score"))["avg"] or 0

        document_tasks = DocumentTask.objects.filter(
            uploaded_by=employee,
            state=0,
            is_active=True,
            task_type="add",
            status="success",
        )
        upload_count = document_tasks.count()
        upload_avg_score = document_tasks.aggregate(avg=Avg("score"))["avg"] or 0

        feedbacks = Feedback.objects.filter(
            username=employee.username, state=0, create_time__gte=feedback_start_date
        )
        feedback_count = feedbacks.count()

        total_avg_score = 0
        total_actions = change_count + upload_count

        if total_actions > 0:
            total_avg_score = (
                change_avg_score * change_count + upload_avg_score * upload_count
            ) / total_actions

        performance_data.append(
            {
                "id": employee.id,
                "name": employee.username,
                "change_count": change_count,
                "change_avg_score": round(change_avg_score, 1),
                "upload_count": upload_count,
                "upload_avg_score": round(upload_avg_score, 1),
                "feedback_count": feedback_count,
                "total_avg_score": round(total_avg_score, 1),
                "total_actions": total_actions,
            }
        )

    performance_data.sort(key=lambda x: x["total_avg_score"], reverse=True)

    for i, data in enumerate(performance_data):
        data["rank"] = i + 1

    chart_data = {
        "employees": [emp["name"] for emp in performance_data],
        "change_scores": [emp["change_avg_score"] for emp in performance_data],
        "upload_scores": [emp["upload_avg_score"] for emp in performance_data],
        "total_scores": [emp["total_avg_score"] for emp in performance_data],
        "total_actions": [emp["total_actions"] for emp in performance_data],
    }

    total_stats_json = json.dumps(
        [
            total_stats["change_count"],
            total_stats["upload_count"],
            total_stats["feedback_count"],
        ]
    )
    context = {
        "performance_data": performance_data,
        "total_stats": total_stats,
        "chart_data_json": json.dumps(chart_data, cls=DjangoJSONEncoder),
        "total_stats_json": total_stats_json,
        "current_month": datetime.now().strftime("%Y年%m月"),
    }

    return render(request, "adminpanel/employee_performance_dashboard.html", context)


@staff_member_required
@user_passes_test(is_superuser)
def get_employee_detail(request, employee_id):
    feedback_start_date = timezone.make_aware(datetime(2025, 3, 1))
    try:
        employee = CustomUser.objects.get(id=employee_id)

        change_logs = ChangeLog.objects.filter(modified_by=employee, state=0)
        change_count = change_logs.count()
        change_avg_score = change_logs.aggregate(avg=Avg("score"))["avg"] or 0

        document_tasks = DocumentTask.objects.filter(
            uploaded_by=employee,
            state=0,
            is_active=True,
            task_type="add",
            status="success",
        )
        upload_count = document_tasks.count()
        upload_avg_score = document_tasks.aggregate(avg=Avg("score"))["avg"] or 0

        feedbacks = Feedback.objects.filter(
            username=employee.username, state=0, create_time__gte=feedback_start_date
        )
        feedback_count = feedbacks.count()

        total_avg_score = 0
        total_actions = change_count + upload_count

        if total_actions > 0:
            total_avg_score = (
                change_avg_score * change_count + upload_avg_score * upload_count
            ) / total_actions

        change_timeline = []
        for log in change_logs:
            change_timeline.append(
                {
                    "date": log.timestamp.strftime("%Y-%m-%d"),
                    "score": log.score or 0,
                    "type": "修改",
                }
            )
        upload_timeline = []
        for task in document_tasks:
            upload_timeline.append(
                {
                    "date": task.created_at.strftime("%Y-%m-%d"),
                    "score": task.score or 0,
                    "type": "上传",
                }
            )

        activity_timeline = sorted(
            change_timeline + upload_timeline, key=lambda x: x["date"], reverse=True
        )

        response_data = {
            "success": True,
            "employee": {
                "id": employee.id,
                "name": employee.username,
                "change_count": change_count,
                "change_avg_score": round(change_avg_score, 1),
                "upload_count": upload_count,
                "upload_avg_score": round(upload_avg_score, 1),
                "feedback_count": feedback_count,
                "total_avg_score": round(total_avg_score, 1),
                "total_actions": total_actions,
            },
            "activity_timeline": activity_timeline[:10],  # 只返回最近10条
        }

        return JsonResponse(response_data)

    except CustomUser.DoesNotExist:
        return JsonResponse({"success": False, "error": "员工不存在"})


@staff_member_required
@user_passes_test(is_superuser)
def export_performance_report(request):
    csv_buffer = StringIO()
    writer = csv.writer(csv_buffer)

    writer.writerow(
        [
            "员工姓名",
            "修改次数",
            "修改平均分",
            "上传次数",
            "上传平均分",
            "反馈次数",
            "总行动次数",
            "总平均分",
        ]
    )

    employees = CustomUser.objects.all()
    feedback_start_date = timezone.make_aware(datetime(2025, 3, 1))

    for employee in employees:
        change_logs = ChangeLog.objects.filter(modified_by=employee, state=0)
        change_count = change_logs.count()
        change_avg_score = change_logs.aggregate(avg=Avg("score"))["avg"] or 0

        document_tasks = DocumentTask.objects.filter(
            uploaded_by=employee,
            state=0,
            is_active=True,
            task_type="add",
            status="success",
        )
        upload_count = document_tasks.count()
        upload_avg_score = document_tasks.aggregate(avg=Avg("score"))["avg"] or 0

        feedbacks = Feedback.objects.filter(
            username=employee.username, state=0, create_time__gte=feedback_start_date
        )
        feedback_count = feedbacks.count()

        total_avg_score = 0
        total_actions = change_count + upload_count

        if total_actions > 0:
            total_avg_score = (
                change_avg_score * change_count + upload_avg_score * upload_count
            ) / total_actions

        writer.writerow(
            [
                employee.username,
                change_count,
                round(change_avg_score, 1),
                upload_count,
                round(upload_avg_score, 1),
                feedback_count,
                total_actions,
                round(total_avg_score, 1),
            ]
        )

    response = HttpResponse(csv_buffer.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="员工_截止{datetime.now().strftime("%Y%m")}_绩效表.csv"'
    )

    csv_buffer.close()

    return response
