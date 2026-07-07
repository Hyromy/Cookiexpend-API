from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps._auth import urls as auth_urls
from apps._catalog import urls as catalog_urls
from apps.store_mgmt import urls as store_mgmt_urls

urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/", include(auth_urls)),
    path("api/", include(catalog_urls)),
    path("api/store-mgmt/", include(store_mgmt_urls)),
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
