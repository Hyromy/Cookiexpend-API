from rest_framework.routers import DefaultRouter

from apps._catalog import views

router = DefaultRouter()
router.register(r"categories", views.CategoryViewSet, basename="category")
router.register(r"presentations", views.PresentationViewSet, basename="presentation")
router.register(r"galeria", views.GaleriaViewSet, basename="galeria")
router.register(r"faqs", views.FAQViewSet, basename="faq")
router.register(r"departments", views.DepartmentViewSet, basename="department")
router.register(r"retailers", views.RetailerViewSet, basename="retailer")

urlpatterns = router.urls
