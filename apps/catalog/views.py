from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps._api.mixins import MixinViewSet
from apps._auth.permissions import any_of, permission
from apps._mail.mails import send_mail
from apps.catalog import models, serializers

CATALOG_PERMISSIONS = [
    any_of(
        permission(user=["Public"], can=["see"]),
        permission(user=["Factory manager"], can=["see", "create", "update", "delete"]),
    )
]


class CategoryViewSet(MixinViewSet):
    model_name = "category"
    queryset = models.Category.objects.all().order_by("order")
    serializer_class = serializers.CategorySerializer
    permission_classes = CATALOG_PERMISSIONS


class PresentationViewSet(MixinViewSet):
    model_name = "presentation"
    queryset = models.Presentation.objects.all()
    serializer_class = serializers.PresentationSerializer
    permission_classes = CATALOG_PERMISSIONS


class GalleryViewSet(MixinViewSet):
    model_name = "gallery_item"
    queryset = models.GalleryItem.objects.all()
    serializer_class = serializers.GalleryItemSerializer
    permission_classes = CATALOG_PERMISSIONS


class FAQViewSet(MixinViewSet):
    model_name = "faq"
    queryset = models.FAQ.objects.all()
    serializer_class = serializers.FAQSerializer
    permission_classes = CATALOG_PERMISSIONS


class SubjectViewSet(MixinViewSet):
    model_name = "subject"
    queryset = models.Subject.objects.all()
    serializer_class = serializers.SubjectSerializer
    permission_classes = CATALOG_PERMISSIONS
    filterset_fields = ["department"]


class DepartmentViewSet(MixinViewSet):
    model_name = "department"
    queryset = models.Department.objects.all().prefetch_related("subjects")
    serializer_class = serializers.DepartmentSerializer
    permission_classes = CATALOG_PERMISSIONS

    @action(detail=True, methods=["post"], url_path="contact", permission_classes=[AllowAny])
    def contact(self, request, pk=None):
        department = self.get_object()

        serializer = serializers.ContactMessageSerializer(
            data=request.data, context={"department": department}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if not department.email:
            return Response(
                {"detail": "This department has no destination email configured."}, status=503
            )

        send_mail(
            template="contact.html",
            ctx={
                "department_name": department.name,
                "subject_label": data["subject"].label,
                "sender_name": data["name"],
                "sender_email": data["email"],
                "sender_phone": data["phone"],
                "sender_city": data["city"],
                "message": data["message"],
            },
            subject=f"New contact message: {data['subject'].label}",
            to=[department.email],
            reply_to=[data["email"]],
        )
        return Response({"detail": "Message sent."}, status=200)


class BrandViewSet(MixinViewSet):
    model_name = "brand"
    queryset = models.Brand.objects.all()
    serializer_class = serializers.BrandSerializer
    permission_classes = CATALOG_PERMISSIONS


class RetailerViewSet(MixinViewSet):
    model_name = "retailer"
    queryset = models.Retailer.objects.all()
    serializer_class = serializers.RetailerSerializer
    permission_classes = CATALOG_PERMISSIONS
