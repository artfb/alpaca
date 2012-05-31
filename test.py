#!/usr/bin/env python

import unittest
import hmac
import hashlib
import datetime
import simplejson
from alpaca import create_application
from alpaca.tracker.models import User, Error

class ApiTestCase(unittest.TestCase):

    def setUp(self):
        # Create application
        self.application = create_application(override_configuration={
            'TESTING': True,
            'ERROR_OCCURRENCE_HISTORY_LIMIT': 30,
            'REPORTERS': {
                'test1': 'test1_api_key',
                'test2': 'test2_api_key',
            },
        })
        self.client = self.application.test_client()

    def tearDown(self):
        Error.objects.all().delete()
        User.objects.all().delete()

    def test_minimal_report(self):
        error_date = datetime.datetime.utcnow()
        message = dict(
            error_hash='error_hash_1',
            traceback="Some traceback",
            date=error_date.isoformat(),
            uri='',
            get_data={},
            post_data={},
            cookies={},
            headers={}
        )
        message_json = simplejson.dumps(message)
        response = self.client.post(
            path='/api/report',
            data=message_json,
            content_type='application/json',
            headers={
                'X-Alpaca-Reporter': 'test1',
                'X-Alpaca-Signature': hmac.new(
                    'test1_api_key', message_json, hashlib.sha256
                ).hexdigest(),
            }
        )
        self.assertEqual(response.status_code, 200)
        # MongoDB stores only 3-digit microseconds, so round the date for
        # comparsion.
        error_date = datetime.datetime(
            error_date.year,
            error_date.month,
            error_date.day,
            error_date.hour,
            error_date.minute,
            error_date.second,
            ((error_date.microsecond / 1000) * 1000)
        )
        # Check the error
        error = Error.objects.get(hash='error_hash_1')
        self.assertGreater(len(error.summary), 0)
        self.assertItemsEqual(error.reporters, ['test1'])
        self.assertEqual(error.traceback, "Some traceback")
        self.assertEqual(error.last_occurrence, error_date)
        self.assertEqual(error.occurrence_counter, 1)
        self.assertEqual(len(error.occurrences), 1)
        # Check the occurrence
        occurrence = error.occurrences[0]
        self.assertEqual(occurrence.date, error_date)
        self.assertEqual(occurrence.reporter, 'test1')

    def test_simple_report(self):
        error_date = datetime.datetime.utcnow()
        message = dict(
            error_hash='error_hash_1',
            traceback="Some traceback",
            date=error_date.isoformat(),
            uri='http://example.com/some/uri',
            get_data={
                'get_parameter_1': 'get_value_1',
                'get_parameter_2': 'get_value_2',
            },
            post_data={
                'post_parameter_1': 'post_value_1',
                'post_parameter_2': 'post_value_2',
            },
            cookies={
                'cookie1': 'cookie1_value',
                'cookie2': 'cookie2_value',
            },
            headers={
                'header1': 'header1_value',
                'header2': 'header2_value',
            }
        )
        message_json = simplejson.dumps(message)
        response = self.client.post(
            path='/api/report',
            data=message_json,
            content_type='application/json',
            headers={
                'X-Alpaca-Reporter': 'test1',
                'X-Alpaca-Signature': hmac.new(
                    'test1_api_key', message_json, hashlib.sha256
                ).hexdigest(),
            }
        )
        self.assertEqual(response.status_code, 200)
        # MongoDB stores only 3-digit microseconds, so round the date for
        # comparsion.
        error_date = datetime.datetime(
            error_date.year,
            error_date.month,
            error_date.day,
            error_date.hour,
            error_date.minute,
            error_date.second,
            ((error_date.microsecond / 1000) * 1000)
        )
        # Check the error
        error = Error.objects.get(hash='error_hash_1')
        self.assertGreater(len(error.summary), 0)
        self.assertItemsEqual(error.reporters, ['test1'])
        self.assertEqual(error.traceback, "Some traceback")
        self.assertEqual(error.last_occurrence, error_date)
        self.assertEqual(error.occurrence_counter, 1)
        self.assertEqual(len(error.occurrences), 1)
        # Check the occurrence
        occurrence = error.occurrences[0]
        self.assertEqual(occurrence.date, error_date)
        self.assertEqual(occurrence.reporter, 'test1')
        self.assertEqual(occurrence.uri, message['uri'])
        self.assertItemsEqual(
            occurrence.get_data,
            map(list, message['get_data'].items())
        )
        self.assertItemsEqual(
            occurrence.post_data,
            map(list, message['post_data'].items())
        )
        self.assertItemsEqual(
            occurrence.cookies,
            map(list, message['cookies'].items())
        )
        self.assertItemsEqual(
            occurrence.headers,
            map(list, message['headers'].items())
        )

    def test_occurrence_history_limit(self):
        def send_occurrence():
            message = dict(
                error_hash='error_hash_1',
                traceback="Some traceback",
                date=datetime.datetime.utcnow().isoformat(),
                uri='',
                get_data={},
                post_data={},
                cookies={},
                headers={}
            )
            message_json = simplejson.dumps(message)
            response = self.client.post(
                path='/api/report',
                data=message_json,
                content_type='application/json',
                headers={
                    'X-Alpaca-Reporter': 'test1',
                    'X-Alpaca-Signature': hmac.new(
                        'test1_api_key', message_json, hashlib.sha256
                    ).hexdigest(),
                }
            )
            self.assertEqual(response.status_code, 200)
        occurrence_range = range(
            2,
            (2 * self.application.config['ERROR_OCCURRENCE_HISTORY_LIMIT']) + 1
        )
        send_occurrence()
        error = Error.objects.get(hash='error_hash_1')
        self.assertEqual(error.occurrence_counter, 1)
        for i in occurrence_range:
            send_occurrence()
            error.reload()
            self.assertEqual(error.occurrence_counter, i)
            self.assertEqual(
                len(error.occurrences),
                min(
                    self.application.config['ERROR_OCCURRENCE_HISTORY_LIMIT'],
                    i
                )
            )

if __name__ == '__main__':
    unittest.main()
