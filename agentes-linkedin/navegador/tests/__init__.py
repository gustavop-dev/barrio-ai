"""The navegador service's tests. Each test gets LIMIT seconds of real time, setup, cleanups and its event loop's close
included: one that hangs prints where every thread is and ends the run with an error, instead of holding CI until
someone cancels it. Loaded before any test module (`python -m unittest discover -s tests -t .`)."""
import faulthandler
import sys
import unittest

LIMIT = 60  # seconds; the whole suite takes about ten
_depth = 0


def _limited(run):
    def limited_run(self, result=None):
        global _depth
        if _depth == 0:  # the outermost run: IsolatedAsyncioTestCase.run wraps TestCase.run
            faulthandler.dump_traceback_later(LIMIT, exit=True, file=sys.stderr)
        _depth += 1
        try:
            return run(self, result)
        finally:
            _depth -= 1
            if _depth == 0:
                faulthandler.cancel_dump_traceback_later()
    return limited_run


unittest.TestCase.run = _limited(unittest.TestCase.run)
unittest.IsolatedAsyncioTestCase.run = _limited(unittest.IsolatedAsyncioTestCase.run)
