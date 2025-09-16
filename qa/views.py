import uuid
import json
import requests
from django.http import JsonResponse, StreamingHttpResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404, render
from feedback_app.models import Record, Feedback
from feedback_app.views import async_search_from_7002
import httpx
import asyncio
from openai import OpenAI
from dashscope import Generation
import re
import time
from django.views.decorators.clickjacking import xframe_options_exempt
from django.core.cache import cache
# import pandas as pd
# import json
# from django.shortcuts import render
# from django.conf import settings
# from django.template.defaulttags import register

API_KEY = "sk-d30b492e49d34c5c98d473b71da46829"


def stream_qwen_response(messages):
    """流式调用大模型生成响应"""
    client = OpenAI(
        api_key=API_KEY, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )

    stream = client.chat.completions.create(
        # model="qwen3-235b-a22b", # 目前最强大
        # model="qwen3-14b",
        # model="qwen3-1.7b",
        model="qwen-max",  # 目前最快
        messages=messages,
        stream=True,
        stream_options={"include_usage": True},
    )

    full_content = ""
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            content_chunk = chunk.choices[0].delta.content
            full_content += content_chunk
            yield json.dumps({"chunk": content_chunk})

    yield json.dumps({"complete": True, "full_content": full_content})


def qa_page(request):
    return render(request, "qa_test.html")


@xframe_options_exempt
def route_page(request):
    return render(request, "zhangbi_amap_api.html")


def remove_emoji(text):
    emoji_pattern = re.compile(
        "["
        "\U0001f600-\U0001f64f"  # 表情
        "\U0001f300-\U0001f5ff"  # 符号 & 图形
        "\U0001f680-\U0001f6ff"  # 交通 & 地图符号
        "\U0001f1e0-\U0001f1ff"  # 旗帜
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub(r"", text)


def remove_markdown(text):
    """移除 Markdown 格式符号"""
    # 移除标题、粗体、斜体、列表等常用Markdown符号
    text = re.sub(r"#{1,6}\s+", "", text)  # 移除 # 标题
    text = re.sub(r"\*\*([^\*]+)\*\*", r"\1", text)  # 移除 **粗体**
    text = re.sub(r"\*([^\*]+)\*", r"\1", text)  # 移除 *斜体*
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)  # 移除 - 或 * 列表
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)  # 移除有序列表
    text = text.replace("\n", " ").replace("\r", "")  # 将换行符替换为空格
    return text


@csrf_exempt
def ask_question(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request method"})

    try:
        start_time = time.time()
        data = json.loads(request.body)
        username = data.get("username", "guest")
        question = data.get("question", "")

        # 1. 调用异步检索接口
        search_start = time.time()
        search_res = asyncio.run(async_search_from_7002(question))
        search_time = time.time() - search_start
        print(f"检索耗时: {search_time:.2f} 秒")
        references = search_res.get("results", [])[:10]

        # 如果没有检索到，也提供默认回答（防止 SSE 报错）
        if not references:
            references = [{"content": "暂无相关资料。"}]
        messages = [
            {
                "role": "system",
                "content": """你是张壁古堡景区智慧导游"奎木狼"，请为游客提供专业、友好、有人情味的讲解。
                回答要求：
                1. 简洁明了，重点突出，控制在300字以内
                2. 只回复与游客问题相关的内容,禁止编造不存在的内容
                3. 如果没有相关资料，明确告诉游客"暂无相关资料，您可以咨询景区工作人员获取更多信息"
                4. 语气自然、温暖、引导式
                5. 使用自然段落格式，适当分段
                6. 保持口语化、亲切的表达方式
                7. 必须合法、安全，不涉及政治敏感或违法内容
                8. 时刻表明奎木狼是张壁古堡智慧导游的身份。""",
            },
            {
                "role": "user",
                "content": f"""
                游客问题：{question}
                参考资料：{json.dumps(references, ensure_ascii=False)}
                请根据以上信息提供简洁明了的回答。
                """,
            },
        ]

        # # 3. 流式生成模型回答
        # def generate():
        #     full_answer = ""
        #     model_start = time.time()
        #     for chunk in stream_qwen_response(messages):
        #         data_chunk = json.loads(chunk)
        #         if "chunk" in data_chunk:
        #             full_answer += data_chunk["chunk"]
        #             yield f"data: {json.dumps({'chunk': data_chunk['chunk']})}\n\n"
        #         elif data_chunk.get("complete"):
        #             full_answer = data_chunk.get("full_content", full_answer)
        #             model_time = time.time() - model_start
        #             print(f"模型生成耗时: {model_time:.2f}秒")
        #             yield f"data: {json.dumps({'complete': True, 'full_content': full_answer})}\n\n"

        #     clean_answer = remove_markdown(remove_emoji(full_answer))
        #     # 4. 存数据库
        #     db_start = time.time()
        #     record = Record.objects.create(
        #         record_uuid=uuid.uuid4().hex,
        #         username=username,
        #         question=question,
        #         answer=clean_answer,  # 存储自然语言回答
        #     )
        #     db_time = time.time() - db_start
        #     print(f"数据库存储耗时: {db_time:.2f}秒")

        #     # 5. 返回最终 record 信息
        #     yield f"data: {json.dumps({'record_id': record.id, 'record_uuid': record.record_uuid, 'references': references})}\n\n"
        def generate():
            full_answer = ""
            model_start = time.time()
            for chunk in stream_qwen_response(messages):
                data_chunk = json.loads(chunk)
                if "chunk" in data_chunk:
                    full_answer += data_chunk["chunk"]
                    yield f"data: {json.dumps({'chunk': data_chunk['chunk']})}\n\n"
                elif data_chunk.get("complete"):
                    full_answer = data_chunk.get("full_content", full_answer)
                    model_time = time.time() - model_start
                    print(f"模型生成耗时: {model_time:.2f}秒")

                    # 4. 存数据库 (保持不变)
                    db_start = time.time()
                    record = Record.objects.create(
                        record_uuid=uuid.uuid4().hex,
                        username=username,
                        question=question,
                        answer=full_answer,  # 存储完整回答
                    )
                    db_time = time.time() - db_start
                    print(f"数据库存储耗时: {db_time:.2f}秒")

                    # 5. 返回最终信息，包含完整内容、record_id 和 references
                    yield f"""data: {
                        json.dumps(
                            {
                                "complete": True,
                                "full_content": full_answer,
                                "record_id": record.id,
                                "record_uuid": record.record_uuid,
                                "references": references,
                            }
                        )
                    }\n\n"""

        total_time = time.time() - start_time
        print(f"总耗时: {total_time:.2f}秒")

        response = StreamingHttpResponse(generate(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"  # nginx 缓冲关闭
        return response

    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)})


@csrf_exempt
def submit_feedback(request, record_id):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            username = data.get("username", "guest")
            state = data.get("state", 0)  # 0=点踩，1=点赞
            reason = data.get("reason", "none")

            record = get_object_or_404(Record, id=record_id)

            fb = Feedback.objects.create(
                record=record, username=username, state=state, feedback_answer=reason
            )

            return JsonResponse({"status": "success", "feedback_id": fb.id})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)})

    return JsonResponse({"status": "error", "message": "Invalid request method"})


@csrf_exempt
def proxy_image(request, image_name):
    # 检查缓存
    cache_key = f"image_{image_name}"
    cached_content = cache.get(cache_key)

    if cached_content:
        return HttpResponse(cached_content, content_type="image/jpeg")

    # B服务器图片URL
    b_server_url = f"http://183.203.208.34:7002/images/{image_name}"

    try:
        # 向B服务器请求图片
        response = requests.get(b_server_url, stream=True, timeout=10)

        if response.status_code == 200:
            content = response.content
            # 缓存图片（设置1小时过期）
            cache.set(cache_key, content, 3600)

            return HttpResponse(
                content, content_type=response.headers.get("Content-Type", "image/jpeg")
            )
        else:
            return HttpResponse(
                f"图片获取失败，状态码: {response.status_code}",
                status=response.status_code,
            )

    except requests.exceptions.RequestException as e:
        return HttpResponse(f"图片代理请求失败: {str(e)}", status=500)
