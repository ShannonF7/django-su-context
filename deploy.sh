#!/bin/bash

echo "🔄 部署 Django 服务..."

# 1. 收集静态资源
echo "📦 收集静态资源..."
/home/lab420pro/tsn/venv/bin/python /home/lab420pro/tsn/feedback_project/manage.py collectstatic --noinput

# 2. 配置 Nginx
echo "🌀 配置 Nginx..."
sudo ln -sf $(pwd)/nginx.feedback.conf /etc/nginx/sites-enabled/feedback_project_8001
sudo /usr/local/nginx/sbin/nginx -t && sudo systemctl reload nginx

# 3. 清理旧日志
echo "🧹 清理旧日志..."
find /home/lab420pro/tsn/feedback_project/ -name "*.log" -mtime +7 -exec rm -f {} \;

# 4. 配置 Gunicorn systemd 服务
echo "🚀 配置 Gunicorn Systemd 服务..."
sudo cp feedback_project.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart feedback_project
sudo systemctl enable feedback_project

echo "✅ 部署完成！访问 http://221.180.19.170:8010 查看效果。"