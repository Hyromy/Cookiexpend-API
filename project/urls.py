from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

from apps._auth import urls as auth_urls
from apps.catalog import urls as catalog_urls
from apps.sistemaMedicionIoT import urls as sistema_medicion_iot_urls
from apps.store_mgmt import urls as store_mgmt_urls

urlpatterns = [
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    path("admin/", admin.site.urls),
    path("auth/", include(auth_urls)),
    path("api/catalog/", include(catalog_urls)),
    path("api/store-mgmt/", include(store_mgmt_urls)),
    path("api/sistema-medicion-iot/", include(sistema_medicion_iot_urls)),

]
