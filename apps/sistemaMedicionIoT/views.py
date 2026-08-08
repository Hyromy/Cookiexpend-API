from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import MeasurementSerializer
from rest_framework.permissions import AllowAny

# Create your views here.
class MeasurementCreateAPIView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):

        serializer = MeasurementSerializer(
            data=request.data
        )

        if serializer.is_valid():

            serializer.save()

            return Response(
                {
                    "success": True,
                    "data": serializer.data
                },
                status=status.HTTP_201_CREATED
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )