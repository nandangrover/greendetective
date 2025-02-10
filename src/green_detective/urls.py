"""
URL configuration for green_detective project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

import os
from django.conf.urls.static import static
from django.urls import include, path, re_path
from django.views.static import serve
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from green_detective import settings
from detective.admin import admin_site


v1_urlpatterns = [
    path("dap/", admin_site.urls),
    path("api/v1/detective/", include("detective.urls")),
    path("api/v1/token", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/v1/token/refresh", TokenRefreshView.as_view(), name="token_refresh"),
    re_path(r"^static/(?P<path>.*)$", serve, {"document_root": settings.STATIC_ROOT}),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns = []

urlpatterns += v1_urlpatterns

v1_schema_view = get_schema_view(
    openapi.Info(
        title="GreenDetective API",
        default_version="v1",
        description="API schema for GreenDetective",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="info@detective.ai"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
    patterns=v1_urlpatterns,
    # TODO If v2 in path do not include it in the schema
)

documentation_urls = [
    path(
        "api/v1/swagger<format>/", v1_schema_view.without_ui(cache_timeout=0), name="schema-json"
    ),
    path(
        "api/v1/swagger/",
        v1_schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path("api/v1/redoc/", v1_schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
]

if os.getenv("SERVER_ENVIRONMENT", None) == "local":
    urlpatterns += documentation_urls

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
