import logging
import time
import uuid
logger=logging.getLogger('team_backend.http')

class RequestIdMiddleware:
    def __init__(self,get_response):self.get_response=get_response
    def __call__(self,request):
        request.request_id=str(uuid.uuid4());start=time.monotonic()
        response=self.get_response(request)
        response['X-Request-ID']=request.request_id
        # Never log headers, query strings, request bodies or generated answers.
        logger.info('request_id=%s method=%s status=%s duration_ms=%.1f',request.request_id,request.method,response.status_code,(time.monotonic()-start)*1000)
        return response
