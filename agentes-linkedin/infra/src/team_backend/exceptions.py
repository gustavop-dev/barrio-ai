from rest_framework.views import exception_handler
from rest_framework.exceptions import APIException
from rest_framework.response import Response

class Conflict(APIException):
    status_code=409
    default_detail='La solicitud entra en conflicto con el estado actual'

def handle_exception(exc,context):
    if isinstance(exc,ValueError):return Response({'detail':str(exc)},status=400)
    return exception_handler(exc,context)
