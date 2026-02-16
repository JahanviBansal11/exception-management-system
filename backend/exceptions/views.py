from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Exception
from .serializers import ExceptionSerializer


class ExceptionViewSet(viewsets.ModelViewSet):
    queryset = Exception.objects.all()
    serializer_class = ExceptionSerializer

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        exception = self.get_object()
        exception.submit(request.user)
        return Response({"message": "Exception submitted"})

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        exception = self.get_object()
        exception.approve(request.user)
        return Response({"message": "Exception approved"})

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        exception = self.get_object()
        exception.reject(request.user)
        return Response({"message": "Exception rejected"})

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        exception = self.get_object()
        exception.close(request.user)
        return Response({"message": "Exception closed"})
