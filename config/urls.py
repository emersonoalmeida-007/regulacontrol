from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from licencas import api

router = DefaultRouter()
router.register("licencas", api.LicencaViewSet, basename="api-licencas")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("entrar/", auth_views.LoginView.as_view(redirect_authenticated_user=True), name="login"),
    path("sair/", auth_views.LogoutView.as_view(), name="logout"),
    path("api/resumo/", api.resumo, name="api-resumo"),
    path("api/", include(router.urls)),
    path("", include("licencas.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
