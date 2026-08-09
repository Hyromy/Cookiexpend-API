from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import BasePermission

from apps._auth.permissions import permission

from .models import Measurement
from .serializers import MeasurementSerializer


class MeasurementPermission(BasePermission):

    def has_permission(self, request, view):

        if request.method == "GET":
            return permission(
                user=["Factory manager", "Store manager"],
                can=["see"],
            )().has_permission(request, view)

        if request.method == "POST":
            return permission(
                user=["Bot"],
                can=["create"],
            )().has_permission(request, view)

        return False


@api_view(["GET", "POST"])
@permission_classes([MeasurementPermission])
def measurements(request):

    if request.method == "GET":
        measurements = Measurement.objects.all()

        serializer = MeasurementSerializer(
            measurements,
            many=True,
        )

        return Response(
            {
                "success": True,
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    if request.method == "POST":
        serializer = MeasurementSerializer(
            data=request.data,
        )

        if serializer.is_valid():
            serializer.save()

            return Response(
                {
                    "success": True,
                    "data": serializer.data,
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )