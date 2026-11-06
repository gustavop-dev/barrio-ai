"""Test doubles for the Anthropic SDK transport used by knowledge.providers.claude."""
from types import SimpleNamespace
import anthropic
import httpx2

def message(text='Consejo [LI-01-M001-K01]',input_tokens=100,output_tokens=20,stop_reason='end_turn',cache_write=0,cache_read=0):
    return SimpleNamespace(content=[SimpleNamespace(type='text',text=text)],stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=input_tokens,output_tokens=output_tokens,
                              cache_creation_input_tokens=cache_write,cache_read_input_tokens=cache_read))

def timeout_error():
    return anthropic.APITimeoutError(request=httpx2.Request('POST','https://api.anthropic.com/v1/messages'))

def status_error(status):
    request=httpx2.Request('POST','https://api.anthropic.com/v1/messages')
    return anthropic.APIStatusError('simulated',response=httpx2.Response(status,request=request),body=None)

class _Stream:
    request_id='req_test'
    def __init__(self,outcome):self.outcome=outcome
    def __enter__(self):return self
    def __exit__(self,*exc):return False
    def get_final_message(self):
        if isinstance(self.outcome,Exception):raise self.outcome
        return self.outcome

class FakeAnthropic:
    """Records calls; count_tokens returns `input_tokens`, stream returns `outcome`."""
    def __init__(self,outcome=None,input_tokens=100,before_generation=None):
        self.calls=[];outer=self
        class Messages:
            def count_tokens(self,**params):
                outer.calls.append(('count_tokens',params))
                return SimpleNamespace(input_tokens=input_tokens)
            def stream(self,**params):
                outer.calls.append(('stream',params))
                if before_generation:before_generation()
                return _Stream(outcome if outcome is not None else message())
        self.messages=Messages()
