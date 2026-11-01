from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.views.generic import View

from .forms import AuthForm, RegistrationForm


class AuthView(View):
    """Авторизация"""

    @staticmethod
    def get(request):
        return render(request, "user/auth.html", {"form": AuthForm()})

    @staticmethod
    def post(request):
        form = AuthForm(request.POST)
        if not form.is_valid():
            return render(
                request,
                "user/auth.html",
                {"form": form, "error": "Проверьте введённые данные."},
            )

        email = form.cleaned_data["email"].strip().lower()
        user = authenticate(
            request, username=email, password=form.cleaned_data["password"]
        )

        if user is not None:
            login(request, user)
            return redirect("dashboard:index")
        return render(
            request,
            "user/auth.html",
            {
                "form": form,
                "error": "Неверный логин или пароль! Повторите попытку.",
            },
        )


class RegistrationView(View):
    """Регистрация"""

    @staticmethod
    def get(request):
        return render(request, "user/registration.html", {"form": RegistrationForm()})

    @staticmethod
    def post(request):
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            if user is not None:
                login(request, user)
            return redirect("dashboard:index")

        non_field = form.non_field_errors()
        error = non_field[0] if non_field else "Проверьте введённые данные."
        return render(
            request,
            "user/registration.html",
            {"form": form, "error": error},
        )


class LogoutView(View):
    """Выход"""

    @staticmethod
    def get(request):
        logout(request)
        return redirect("dashboard:index")
