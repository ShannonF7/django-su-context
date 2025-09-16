#!/usr/bin/env python
"""
监控Celery任务状态的脚本
"""
import os
import sys
import django
import time
from datetime import datetime

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'feedback_project.settings')
django.setup()

from feedback_app.models import DocumentTask

def monitor_celery_tasks():
    """监控Celery任务状态"""
    print("开始监控Celery任务状态...")
    print("按 Ctrl+C 停止监控")
    print("-" * 80)
    
    try:
        while True:
            # 获取所有活跃的任务
            tasks = DocumentTask.objects.filter(is_active=True).order_by('-updated_at')[:10]
            
            # 清屏
            os.system('clear' if os.name == 'posix' else 'cls')
            
            print(f"Celery任务监控 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("-" * 80)
            print(f"{'ID':<5} {'类型':<8} {'状态':<10} {'更新时间':<20} {'消息':<30}")
            print("-" * 80)
            
            for task in tasks:
                status_icon = {
                    'pending': '⏳',
                    'success': '✅',
                    'failed': '❌'
                }.get(task.status, '❓')
                
                print(f"{task.id:<5} {task.task_type:<8} {status_icon} {task.status:<8} {task.updated_at.strftime('%Y-%m-%d %H:%M:%S'):<20} {task.message[:28]:<30}")
            
            print("-" * 80)
            print("状态说明: ⏳ 处理中 | ✅ 成功 | ❌ 失败")
            print("按 Ctrl+C 停止监控")
            
            # 等待2秒
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("\n监控已停止")

def show_task_details(task_id):
    """显示特定任务的详细信息"""
    try:
        task = DocumentTask.objects.get(id=task_id, is_active=True)
        print(f"\n任务详情 - ID: {task.id}")
        print("-" * 50)
        print(f"类型: {task.task_type}")
        print(f"状态: {task.status}")
        print(f"文档ID: {task.document_id or '无'}")
        print(f"内容: {task.content[:100]}{'...' if len(task.content) > 100 else ''}")
        print(f"关键词: {task.keywords}")
        print(f"消息: {task.message}")
        print(f"创建时间: {task.created_at}")
        print(f"更新时间: {task.updated_at}")
        print(f"是否活跃: {task.is_active}")
        
    except DocumentTask.DoesNotExist:
        print(f"任务 ID {task_id} 不存在")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # 如果提供了任务ID，显示该任务的详细信息
        try:
            task_id = int(sys.argv[1])
            show_task_details(task_id)
        except ValueError:
            print("请提供有效的任务ID")
    else:
        # 否则开始监控
        monitor_celery_tasks()
