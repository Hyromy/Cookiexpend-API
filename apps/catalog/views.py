from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps._mail.mails import send_mail
from apps.catalog import models, serializers


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Category.objects.all().order_by("order")
    serializer_class = serializers.CategorySerializer
    permission_classes = [AllowAny]


class PresentationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Presentation.objects.all()
    serializer_class = serializers.PresentationSerializer
    permission_classes = [AllowAny]


class GalleryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.GalleryItem.objects.all()
    serializer_class = serializers.GalleryItemSerializer
    permission_classes = [AllowAny]


class FAQViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.FAQ.objects.all()
    serializer_class = serializers.FAQSerializer
    permission_classes = [AllowAny]


class DepartmentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Department.objects.all().prefetch_related("subjects")
    serializer_class = serializers.DepartmentSerializer
    permission_classes = [AllowAny]

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


class RetailerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = models.Retailer.objects.all()
    serializer_class = serializers.RetailerSerializer
    permission_classes = [AllowAny]
