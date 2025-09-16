from celery import shared_task
import httpx
import logging
from .models import DocumentTask

logger = logging.getLogger(__name__)

SERVER_URL = "http://183.203.208.34:7002"
API_TOKEN = "zhangbi123456secure"


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def retry_failed_document_upload_task(self, content, keywords, task_id):
    try:
        # 获取任务并立即更新状态为处理中
        task = DocumentTask.objects.get(id=task_id, is_active=True)
        task.status = "pending"
        task.message = "正在重新处理文档..."
        task.save()
        
        logger.info(f"开始重新处理任务 {task_id}")

        if not keywords:
            task.status = "failed"
            task.message = "Error: Empty keyword list"
            task.save()
            logger.error(f"任务 {task_id} 失败：关键词列表为空")
            return

        payload = {
            "texts": [content],
            "metadatas": [{"keywords": ",".join(keywords)}],
        }

        headers = {
            "Content-Type": "application/json",
            "access-token": API_TOKEN,
        }

        logger.info(f"向服务器 {SERVER_URL}/add_documents/ 发送请求")
        logger.debug(f"请求载荷: {payload}")

        with httpx.Client(timeout=300.0) as client:
            response = client.post(
                f"{SERVER_URL}/add_documents/", json=payload, headers=headers
            )

            logger.info(f"服务器响应状态: {response.status_code}")
            logger.debug(f"服务器响应内容: {response.text}")

            response.raise_for_status()
            result = response.json()

            if result.get("status") == "success":
                document_id = result.get("doc_ids", [None])[0]
                task.status = "success"
                task.document_id = document_id
                task.message = "文档重新添加成功"
                logger.info(f"任务 {task_id} 成功完成，文档ID: {document_id}")
            else:
                error_msg = result.get("message", "Document add failed")
                task.status = "failed"
                task.message = f"服务器错误: {error_msg}"
                logger.error(f"任务 {task_id} 失败：{error_msg}")

            task.save()

    except httpx.RequestError as e:
        # 网络请求错误
        error_msg = f"网络请求错误: {str(e)}"
        logger.error(f"任务 {task_id} 网络错误: {str(e)}", exc_info=True)
        
        try:
            task = DocumentTask.objects.get(id=task_id, is_active=True)
            task.status = "failed"
            task.message = error_msg
            task.save()
        except:
            pass
            
        # 重试网络错误
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error(f"任务 {task_id} 重试次数已用完")
            try:
                task = DocumentTask.objects.get(id=task_id, is_active=True)
                task.status = "failed"
                task.message = f"重试次数已用完: {error_msg}"
                task.save()
            except:
                pass
                
    except httpx.HTTPStatusError as e:
        # HTTP状态错误
        error_msg = f"HTTP错误 {e.response.status_code}: {e.response.text}"
        logger.error(f"任务 {task_id} HTTP错误: {error_msg}", exc_info=True)
        
        try:
            task = DocumentTask.objects.get(id=task_id, is_active=True)
            task.status = "failed"
            task.message = error_msg
            task.save()
        except:
            pass
            
    except Exception as exc:
        # 其他异常
        error_msg = f"处理错误: {str(exc)}"
        logger.error(f"任务 {task_id} 异常: {str(exc)}", exc_info=True)
        
        try:
            task = DocumentTask.objects.get(id=task_id, is_active=True)
            task.status = "failed"
            task.message = error_msg
            task.save()
        except:
            pass
            
        # 重试其他异常
        try:
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error(f"任务 {task_id} 重试次数已用完")
            try:
                task = DocumentTask.objects.get(id=task_id, is_active=True)
                task.status = "failed"
                task.message = f"重试次数已用完: {error_msg}"
                task.save()
            except:
                pass
