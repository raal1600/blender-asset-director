"""Only isolated acquisition transport failures may be retried, at most twice."""
from pathlib import Path
import importlib.util
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('cloud_acceptance',ROOT/'tools/cloud_acceptance.py')
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)


class ProviderRetryTests(unittest.TestCase):
    def test_first_success_needs_no_retry(self):
        operation=Mock(return_value='actual result');sleep=Mock();events=[]
        self.assertEqual(v.retry_provider_call(operation,'acquire',events.append,sleep),'actual result')
        operation.assert_called_once();sleep.assert_not_called()
        self.assertEqual(events,[{'stage':'acquire','attempt':1,'status':'PASS'}])

    def test_transient_failure_and_recovery_both_remain_visible(self):
        for code in v.TRANSIENT_NETWORK_CODES:
            with self.subTest(code=code):
                operation=Mock(side_effect=[v.DirectorError(code,'do not log signed URL'),'actual result'])
                sleep=Mock();events=[]
                self.assertEqual(v.retry_provider_call(operation,'acquire',events.append,sleep),'actual result')
                self.assertEqual([e['status'] for e in events],['FAIL','PASS'])
                self.assertEqual(events[0]['code'],code);sleep.assert_called_once_with(2)
                self.assertNotIn('signed URL',str(events))

    def test_exhaustion_fails_after_three_attempts(self):
        operation=Mock(side_effect=v.DirectorError('CONNECTION_FAILED','redacted'));sleep=Mock();events=[]
        with self.assertRaises(v.DirectorError):v.retry_provider_call(operation,'acquire',events.append,sleep)
        self.assertEqual(operation.call_count,3)
        self.assertEqual([c.args[0] for c in sleep.call_args_list],[2,4])
        self.assertEqual([e['status'] for e in events],['FAIL']*3)

    def test_security_auth_integrity_and_schema_errors_never_retry(self):
        for code in ('UNSAFE_URL','PRIVATE_ADDRESS','AUTH_OR_ACCESS_REQUIRED','CHECKSUM_MISMATCH',
                     'LICENSE_RESTRICTED','PROVIDER_SCHEMA','HTTP_STATUS','UNKNOWN_ERROR'):
            operation=Mock(side_effect=v.DirectorError(code,'redacted'));sleep=Mock();events=[]
            with self.subTest(code=code),self.assertRaises(v.DirectorError):
                v.retry_provider_call(operation,'acquire',events.append,sleep)
            operation.assert_called_once();sleep.assert_not_called()

    def test_assertions_and_programming_errors_never_retry(self):
        for error in (AssertionError('failed QA'),KeyError('invalid response'),OSError('unclassified')):
            operation=Mock(side_effect=error);sleep=Mock()
            with self.subTest(error=type(error).__name__),self.assertRaises(type(error)):
                v.retry_provider_call(operation,'acquire',lambda e:None,sleep)
            operation.assert_called_once();sleep.assert_not_called()

    def test_policy_error_after_network_failure_stops(self):
        operation=Mock(side_effect=[v.DirectorError('NETWORK_ERROR','network'),
                                   v.DirectorError('AUTH_OR_ACCESS_REQUIRED','auth'),'not allowed'])
        events=[];sleep=Mock()
        with self.assertRaises(v.DirectorError):v.retry_provider_call(operation,'acquire',events.append,sleep)
        self.assertEqual(operation.call_count,2);sleep.assert_called_once_with(2)
        self.assertEqual([e['code'] for e in events],['NETWORK_ERROR','AUTH_OR_ACCESS_REQUIRED'])


if __name__=='__main__':unittest.main()
