from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from game.views import CustomPasswordResetView
from django.views.generic import TemplateView
from django.shortcuts import render
from game.forms import CustomSetPasswordForm

urlpatterns = [
    path('admin/', admin.site.urls),
    path('robots.txt', TemplateView.as_view(template_name="robots.txt", content_type="text/plain")),
    path('sitemap.xml', TemplateView.as_view(template_name="sitemap.xml", content_type="application/xml")),
    path('', include('game.urls')),

    path(
        'password-reset/',
        CustomPasswordResetView.as_view(
            template_name='game/password_reset.html',
            email_template_name='game/password_reset_email.html',
            subject_template_name='game/password_reset_subject.txt',
        ),
        name='password_reset'
    ),

    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='game/password_reset_done.html'
         ),
         name='password_reset_done'),

    path('password-reset-confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='game/password_reset_confirm.html',
             form_class=CustomSetPasswordForm
         ),
         name='password_reset_confirm'),

    path('password-reset-complete/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='game/password_reset_complete.html'
         ),
         name='password_reset_complete'),
]


def custom_page_not_found(request, exception):
    """Render the themed 404 page for unresolved routes."""
    return render(request, '404.html', status=404)


def custom_server_error(request):
    """Render the themed 500 page for unexpected server errors."""
    return render(request, '500.html', status=500)


handler404 = 'core.urls.custom_page_not_found'
handler500 = 'core.urls.custom_server_error'
