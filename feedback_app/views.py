import asyncio
from asyncio.log import logger
import json
import threading
import httpx
from datetime import datetime
from django.contrib import messages
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.db.models import Count
from django.views.decorators.csrf import csrf_exempt

from .models import DocumentTask, Record, Feedback, ChangeLog
from .forms import FeedbackEditForm
from .tasks import retry_failed_document_upload_task


@login_required
def record_list(request):
    search_query = request.GET.get("q", "")
    state_filter = request.GET.get("state", "")
    start_date = timezone.make_aware(
        datetime(2025, 3, 1), timezone.get_current_timezone()
    )

    start_date = timezone.make_aware(
        datetime(2025, 3, 1), timezone=timezone.get_current_timezone()
    )

    feedbacks = (
        Feedback.objects.select_related("record")
        .filter(state=0, create_time__gte=start_date)
        .annotate(change_count=Count("changelogs"))
        .order_by("-create_time")
    )

    if search_query:
        feedbacks = feedbacks.filter(record__question__icontains=search_query)

    paginator = Paginator(feedbacks, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "feedback/record_list.html",
        {
            "page_obj": page_obj,
            "search_query": search_query,
            "state_filter": state_filter,
        },
    )


@login_required
def record_detail(request, id):
    record = get_object_or_404(Record, id=id)
    start_date = timezone.make_aware(
        datetime(2025, 3, 1), timezone=timezone.get_current_timezone()
    )

    feedbacks = (
        Feedback.objects.filter(record=record, state=0, create_time__gte=start_date)
        .annotate(change_count=Count("changelogs"))
        .order_by("-create_time")
    )

    if request.method == "POST":
        form = FeedbackEditForm(request.POST)
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.record = record
            feedback.username = request.user.username
            feedback.save()
            messages.success(request, "反馈已成功提交")
            return redirect("feedback:record_detail", id=id)
    else:
        form = FeedbackEditForm()

    return render(
        request,
        "feedback/record_detail.html",
        {
            "title": f"记录详情 - {record.id}",
            "record": record,
            "feedbacks": feedbacks,
            "form": form,
        },
    )


"""
NEW：Search and Update Functions for 7002 Server
"""
SERVER_URL = "http://183.203.208.34:7002"
API_TOKEN = "zhangbi123456secure"


async def async_search_from_7002(query: str) -> dict:
    """Search documents from 7002 server"""
    url = f"{SERVER_URL}/smart_query/"
    payload = {"query": query}
    headers = {
        "Content-Type": "application/json",
        "access-token": API_TOKEN,
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            if "status" not in data:
                data["status"] = "success" if data.get("results") else "error"

            return data
    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error {e.response.status_code}: {e.response.text}"
        return {"status": "error", "message": error_msg}
    except Exception as e:
        error_msg = str(e)
        return {"status": "error", "message": error_msg}


async def async_update_document_on_7002(document_id: str, new_content: str) -> dict:
    """Update document content on 7002 server"""
    url = f"{SERVER_URL}/update_by_id/"
    payload = {"id": document_id, "new_text": new_content}
    headers = {
        "Content-Type": "application/json",
        "access-token": API_TOKEN,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error {e.response.status_code}: {e.response.text}"
        return {"status": "error", "message": error_msg}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@login_required
def edit_feedback(request, feedback_id):
    feedback = get_object_or_404(Feedback, id=feedback_id)
    query = feedback.record.question
    documents_json = "[]"

    try:
        response = asyncio.run(async_search_from_7002(query))
        # print("原始接口返回 JSON：", json.dumps(response, ensure_ascii=False, indent=2))
        data = []
        if response.get("status") == "success":
            for item in response.get("results", []):
                metadata = item.get("metadata", {})
                converted_item = {
                    "id": item.get("id", ""),
                    "content": item.get("content", ""),
                    "metadata": metadata,
                    "title": metadata.get("title", "无标题"),
                    "categories": metadata.get("categories", ""),
                    "position": metadata.get("position", ""),
                    "timestamp": metadata.get("timestamp", ""),
                    "jpg_path": metadata.get("jpg_path", ""),
                    "score": item.get("similarity", 0),
                    "distance": item.get("distance", 0),
                    "match_type": item.get("match_type", "unknown"),
                }

                content = converted_item["content"]
                if not content:
                    continue
                data.append(converted_item)
        else:
            print(f"查询失败: {response.get('message', '未知错误')}")
        documents_json = json.dumps(data, ensure_ascii=False)
        # print("处理后的查询结果 JSON：", documents_json)
        request.session["documents_json"] = documents_json
    except Exception as e:
        print(f"文档处理错误: {str(e)}")
        import traceback

        traceback.print_exc()
        data = []

    if request.method == "POST":
        form = FeedbackEditForm(request.POST)
        if form.is_valid():
            feedback.state = form.cleaned_data["state"]
            feedback.feedback_answer = form.cleaned_data["feedback_answer"]
            feedback.save()
            messages.success(request, "保存成功！")
            return redirect("feedback:edit_feedback", feedback_id=feedback.id)
    else:
        form = FeedbackEditForm(
            initial={
                "state": feedback.state,
                "feedback_answer": feedback.feedback_answer,
            }
        )

    return render(
        request,
        "feedback/edit_feedback_v2.html",
        {
            "form": form,
            "record": feedback.record,
            "feedback": feedback,
            "title": "编辑反馈",
            "documents": data,
            "documents_json": mark_safe(documents_json),
        },
    )


@login_required
def update_reference(request, feedback_id):
    feedback = get_object_or_404(Feedback, id=feedback_id)
    try:
        body = json.loads(request.body)
        doc_id = body["id"]
        old_text = body["old_content"]
        new_text = body["new_content"]
        user = request.user
        now_iso = datetime.now().isoformat()

        update_response = asyncio.run(async_update_document_on_7002(doc_id, new_text))

        if update_response.get("status") != "success":
            raise Exception(update_response.get("message", "更新失败"))

        ChangeLog.objects.create(
            feedback=feedback,
            document_id=doc_id,
            original=old_text,
            modified=new_text,
            modified_by=user,
            timestamp=now_iso,
        )

        return JsonResponse({"status": "success"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@login_required
def upload_page(request, feedback_id):
    feedback = get_object_or_404(
        Feedback.objects.select_related("record"), id=feedback_id
    )
    # Get recent uploads by the user
    recent_uploads = DocumentTask.objects.filter(
        uploaded_by=request.user.id, task_type="add"
    ).order_by("-created_at")[:5]

    return render(
        request,
        "feedback/upload_page.html",
        {"feedback": feedback, "recent_uploads": recent_uploads},
    )


@csrf_exempt
def add_document(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            logger.debug(f"Received data: {data}")
            content = data.get("texts", [""])[0]
            metadatas = data.get("metadatas", [])

            # Check if keywords are empty
            if not metadatas:
                return JsonResponse(
                    {"status": "error", "message": "No metadata provided"},
                    status=400,
                )
            metadata = metadatas[0]
            keywords = metadata.get("keywords", [])

            if isinstance(keywords, str):
                keywords = [kw.strip() for kw in keywords.split(",") if kw.strip()]

            # Verify keywords are provided
            if not keywords:
                return JsonResponse(
                    {"status": "error", "message": "Keywords cannot be empty"},
                    status=400,
                )
            # Verify keywords are non-empty strings
            if not all(isinstance(kw, str) and kw.strip() for kw in keywords):
                return JsonResponse(
                    {
                        "status": "error",
                        "message": "Keywords must be non-empty strings",
                    },
                    status=400,
                )

            # Create task record
            task = DocumentTask.objects.create(
                task_type="add",
                content=content,
                keywords=",".join(keywords),
                status="pending",
                uploaded_by_id=request.user.id,
                is_active=True,
            )

            # Start background thread
            thread = threading.Thread(
                target=async_add_document_on_7002, args=(content, keywords, task.id)
            )
            thread.start()

            return JsonResponse(
                {
                    "status": "processing",
                    "message": "Document processing in background",
                    "task_id": task.id,
                }
            )

        except Exception as e:
            logger.error(f"Document add error: {str(e)}", exc_info=True)
            return JsonResponse(
                {"status": "error", "message": f"Server error: {str(e)}"}, status=500
            )
    return JsonResponse(
        {"status": "error", "message": "Invalid request method"}, status=400
    )


@csrf_exempt
def delete_document(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            document_id = data.get("id")

            # Search for existing add task
            add_task = DocumentTask.objects.filter(
                document_id=document_id,
                task_type="add",
                status="success",
                is_active=True,
            ).first()

            if add_task:
                # Mark the add task as deleted
                add_task.mark_as_deleted()

            task = DocumentTask.objects.create(
                task_type="delete",
                document_id=document_id,
                status="pending",
                uploaded_by_id=request.user.id,
                is_active=True,
            )
            # Start background thread for deletion
            thread = threading.Thread(
                target=async_delete_document_on_7002, args=(document_id, task.id)
            )
            thread.start()

            return JsonResponse(
                {
                    "status": "processing",
                    "message": "Deletion processing in background",
                    "task_id": task.id,
                }
            )

        except Exception as e:
            logger.error(f"Document delete error: {str(e)}", exc_info=True)
            return JsonResponse(
                {"status": "error", "message": f"Server error: {str(e)}"}, status=500
            )
    return JsonResponse(
        {"status": "error", "message": "Invalid request method"}, status=400
    )


def check_task_status(request):
    task_id = request.GET.get("task_id")
    try:
        task = DocumentTask.objects.get(id=task_id, is_active=True)
        return JsonResponse(
            {
                "status": task.status,
                "document_id": task.document_id,
                "message": task.message,
            }
        )
    except DocumentTask.DoesNotExist:
        return JsonResponse(
            {"status": "error", "message": "Task not found"}, status=404
        )


def async_add_document_on_7002(content, keywords, task_id):
    try:
        task = DocumentTask.objects.get(id=task_id, is_active=True)
        url = f"{SERVER_URL}/add_documents/"

        # Double-check keywords aren't empty
        if not keywords:
            task.status = "failed"
            task.message = "Error: Empty keyword list"
            task.save()
            return

        payload = {
            "texts": [content],
            "metadatas": [
                {
                    "keywords": ",".join(keywords)  # Comma separated without spaces
                }
            ],
        }

        headers = {
            "Content-Type": "application/json",
            "access-token": API_TOKEN,
        }

        with httpx.Client(timeout=300.0) as client:
            response = client.post(url, json=payload, headers=headers)

            # Log request details
            logger.info(f"Request to B server: {url}")
            logger.debug(f"Request payload: {json.dumps(payload, ensure_ascii=False)}")
            logger.info(f"Response status: {response.status_code}")
            logger.debug(f"Response content: {response.text}")

            response.raise_for_status()
            result = response.json()

            if result.get("status") == "success":
                document_id = result.get("doc_ids", [])[0]
                task.status = "success"
                task.document_id = document_id
                task.message = "Document added successfully"
            else:
                error_msg = result.get("message", "Document add failed")
                task.status = "failed"
                task.message = f"B server error: {error_msg}"
                logger.error(f"Document add failed: {error_msg}")

            task.save()

    except Exception as e:
        logger.error(f"Async document add failed: {str(e)}", exc_info=True)
        task.status = "failed"
        task.message = f"Processing error: {str(e)}"
        task.save()


def async_delete_document_on_7002(document_id, task_id):
    try:
        task = DocumentTask.objects.get(id=task_id, is_active=True)
        url = f"{SERVER_URL}/delete_document/"
        payload = {"id": document_id}
        headers = {
            "Content-Type": "application/json",
            "access-token": API_TOKEN,
        }

        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=payload, headers=headers)

            # Log request details
            logger.info(f"Request to B server: {url}")
            logger.debug(f"Request payload: {json.dumps(payload, ensure_ascii=False)}")
            logger.info(f"Response status: {response.status_code}")
            logger.debug(f"Response content: {response.text}")

            response.raise_for_status()
            result = response.json()

            if result.get("status") == "success":
                task.status = "success"
                task.message = "Document deleted successfully"
            else:
                error_msg = result.get("message", "Document delete failed")
                task.status = "failed"
                task.message = f"B server error: {error_msg}"
                logger.error(f"Document delete failed: {error_msg}")

            task.save()

    except Exception as e:
        logger.error(f"Async document delete failed: {str(e)}", exc_info=True)
        task.status = "failed"
        task.message = f"Processing error: {str(e)}"
        task.save()


@login_required
def upload_history(request):
    uploads = DocumentTask.objects.filter(
        uploaded_by=request.user.id, task_type="add", is_active=True, state=0
    ).order_by("-updated_at")

    paginator = Paginator(uploads, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    for upload in page_obj:
        upload.keywords_list = upload.keywords.split(",")

    return render(
        request,
        "feedback/upload_history_v0.html",
        {
            "page_obj": page_obj,
            "feedback": Feedback.objects.first(),
        },
    )


@csrf_exempt
def retry_document_upload_view(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            task_id = data.get("task_id")
            if not task_id:
                return JsonResponse(
                    {"status": "error", "message": "task_id required"}, status=400
                )

            try:
                task = DocumentTask.objects.get(id=task_id, is_active=True)
            except DocumentTask.DoesNotExist:
                return JsonResponse(
                    {"status": "error", "message": "Task not found"}, status=404
                )

            content = task.content
            keywords = task.keywords.split(",") if task.keywords else []

            if not content or not keywords:
                return JsonResponse(
                    {"status": "error", "message": "Task content or keywords missing"},
                    status=400,
                )

            task.status = "pending"
            task.message = "正在重新处理..."
            task.save()

            logger.info(f"开始重新上传任务 {task_id}")

            retry_failed_document_upload_task.delay(content, keywords, task.id)

            return JsonResponse(
                {
                    "status": "processing",
                    "message": "重新上传已开始，请稍后刷新查看状态",
                }
            )

        except json.JSONDecodeError:
            return JsonResponse(
                {"status": "error", "message": "Invalid JSON format"}, status=400
            )
        except Exception as e:
            logger.error(f"重新上传错误: {str(e)}", exc_info=True)
            return JsonResponse(
                {"status": "error", "message": f"服务器错误: {str(e)}"}, status=500
            )
    else:
        return JsonResponse(
            {"status": "error", "message": "Invalid method"}, status=405
        )
