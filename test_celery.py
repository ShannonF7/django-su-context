#!/usr/bin/env python
"""
测试Celery任务是否正常工作的脚本
"""
import os
import sys
import django

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'feedback_project.settings')
django.setup()

from feedback_app.tasks import retry_failed_document_upload_task
from feedback_app.models import DocumentTask

def test_celery_task():
    """测试Celery任务是否正常工作"""
    print("开始测试Celery任务...")
    
    # 查找一个失败的任务进行测试
    try:
        failed_task = DocumentTask.objects.filter(
            status='failed', 
            is_active=True
        ).first()
        
        if not failed_task:
            print("没有找到失败的任务，创建一个测试任务...")
            # 创建一个测试任务
            test_task = DocumentTask.objects.create(
                task_type='add',
                status='failed',
                content='这是一个测试文档内容',
                keywords='测试,关键词',
                message='测试任务',
                is_active=True
            )
            task_id = test_task.id
            print(f"创建测试任务 ID: {task_id}")
        else:
            task_id = failed_task.id
            print(f"使用现有失败任务 ID: {task_id}")
        
        # 测试任务内容
        content = "这是一个测试文档内容，用于验证Celery任务是否正常工作。"
        keywords = ["测试", "文档", "Celery"]
        
        print(f"任务ID: {task_id}")
        print(f"内容: {content}")
        print(f"关键词: {keywords}")
        
        # 调用Celery任务
        print("正在调用Celery任务...")
        result = retry_failed_document_upload_task.delay(content, keywords, task_id)
        
        print(f"任务已提交，任务ID: {result.id}")
        print(f"任务状态: {result.status}")
        
        # 等待一段时间后检查结果
        import time
        print("等待5秒后检查任务状态...")
        time.sleep(5)
        
        # 检查任务状态
        try:
            task = DocumentTask.objects.get(id=task_id)
            print(f"数据库中的任务状态: {task.status}")
            print(f"任务消息: {task.message}")
        except DocumentTask.DoesNotExist:
            print("任务不存在")
            
    except Exception as e:
        print(f"测试过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_celery_task()
