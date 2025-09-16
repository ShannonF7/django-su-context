from django.contrib import messages
from django.contrib.auth import login, logout
from django.shortcuts import redirect, render
from django.urls import reverse_lazy, reverse
from django.views.decorators.csrf import csrf_exempt

from .backends import CustomAuthBackend


@csrf_exempt
def user_login(request):
    if request.user.is_authenticated:
        return redirect_user_based_on_role(request.user)

    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        auth_backend = CustomAuthBackend()
        user = auth_backend.authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            request.session.set_expiry(0)

            # 优先使用 POST 或 GET 中的 next 参数
            next_url = request.POST.get("next") or request.GET.get("next")
            if next_url:
                return redirect(next_url)

            return redirect_user_based_on_role(user)
        else:
            messages.error(request, "用户名或密码错误")
    else:
        if "next" in request.GET:
            messages.warning(request, "登录状态已过期，请重新登录")

    return render(request, "registration/login.html")


def redirect_user_based_on_role(user):
    if user.is_superuser:
        return render(None, "redirect_choice.html", {"user": user})
    else:
        return redirect("/feedback/records/")


def user_logout(request):
    logout(request)
    messages.success(request, "已成功登出")
    return redirect("/accounts/login")  # 用户登出后跳转到登录页面