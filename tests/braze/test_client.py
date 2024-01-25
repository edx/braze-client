"""
Tests for Braze client.
"""
import json
import math
from unittest import TestCase

import ddt
import responses

from braze.client import BrazeClient
from braze.constants import (
    GET_EXTERNAL_IDS_CHUNK_SIZE,
    UNSUBSCRIBED_EMAILS_API_LIMIT,
    UNSUBSCRIBED_EMAILS_API_SORT_DIRECTION,
    BrazeAPIEndpoints,
)
from braze.exceptions import (
    BrazeBadRequestError,
    BrazeClientError,
    BrazeForbiddenError,
    BrazeInternalServerError,
    BrazeNotFoundError,
    BrazeRateLimitError,
    BrazeUnauthorizedError,
)


@ddt.ddt
class BrazeClientTests(TestCase):
    """
    Tests for Braze Client.
    """
    BRAZE_URL = 'http://braze-api-url.com'
    CAMPAIGN_SEND_URL = BRAZE_URL + BrazeAPIEndpoints.SEND_CAMPAIGN
    CANVAS_SEND_URL = BRAZE_URL + BrazeAPIEndpoints.SEND_CANVAS
    EXPORT_ID_URL = BRAZE_URL + BrazeAPIEndpoints.EXPORT_IDS
    MESSAGE_SEND_URL = BRAZE_URL + BrazeAPIEndpoints.SEND_MESSAGE
    NEW_ALIAS_URL = BRAZE_URL + BrazeAPIEndpoints.NEW_ALIAS
    USERS_IDENTIFY_URL = BRAZE_URL + BrazeAPIEndpoints.IDENTIFY_USERS
    USERS_TRACK_URL = BRAZE_URL + BrazeAPIEndpoints.TRACK_USER
    UNSUBSCRIBE_USER_EMAIL_URL = BRAZE_URL + BrazeAPIEndpoints.UNSUBSCRIBE_USER_EMAIL
    RETRIEVE_UNSUBSCRIBED_EMAILS = BRAZE_URL + BrazeAPIEndpoints.UNSUBSCRIBED_EMAILS

    def setUp(self):
        super().setUp()
        self.client = self._get_braze_client()
        self.start_date = "2001-01-01"
        self.end_date = "2002-02-02"

    def _get_braze_client(self):
        return BrazeClient(
            api_key='api_key',
            api_url='http://braze-api-url.com',
            app_id='app_id'
        )

    def _mock_braze_error_response(self, status, headers=None, url=EXPORT_ID_URL, request_type="POST"):
        responses.add(
            getattr(responses, request_type),
            url,
            headers=headers or {},
            json={"message": "error"},
            status=status
        )

    @responses.activate
    def test_get_braze_external_id_success(self):
        """
        Tests a successful call to the /users/export/ids endpoint.
        """
        responses.add(
            responses.POST,
            self.EXPORT_ID_URL,
            json={'users': [{'external_id': '1'}], 'message': 'success'},
            status=201
        )
        external_id = self.client.get_braze_external_id(email='test@example.com')

        self.assertEqual(external_id, '1')
        assert len(responses.calls) == 1
        assert responses.calls[0].request.url == self.EXPORT_ID_URL

    @responses.activate
    def test_get_braze_external_id_failure(self):
        """
        Tests a call to the /users/export/ids endpoint with an invalid email.
        """
        responses.add(
            responses.POST,
            self.EXPORT_ID_URL,
            json={'users': [], 'invalid_ids': ['1'], 'message': 'success'},
            status=201
        )
        external_id = self.client.get_braze_external_id(email='test@example.com')

        assert external_id is None
        assert len(responses.calls) == 1
        assert responses.calls[0].request.url == self.EXPORT_ID_URL

    def test_identify_users_bad_args(self):
        """
        Tests that arguments are validated.
        """
        with self.assertRaises(BrazeClientError):
            self.client.identify_users([])

    @responses.activate
    def test_identify_users(self):
        """
        Tests a successful call to the /users/identify endpoint.
        """
        responses.add(
            responses.POST,
            self.USERS_IDENTIFY_URL,
            json={'message': 'success'},
            status=201
        )

        self.client.identify_users([
            {
                'external_id': '1',
                'user_alias': {
                    'alias_name': 'alias_name',
                    'alias_label': 'alias_label'
                }
            }
        ])

        expected_body = {
            "aliases_to_identify": [
                {
                    "external_id": "1",
                    "user_alias": {
                        "alias_name": "alias_name",
                        "alias_label": "alias_label"
                    }
                }
            ]
        }
        assert len(responses.calls) == 1
        assert responses.calls[0].request.url == self.USERS_IDENTIFY_URL
        assert responses.calls[0].request.body == json.dumps(expected_body)

    def test_track_user_bad_args(self):
        """
        Tests that arguments are validated.
        """

        with self.assertRaises(BrazeClientError):
            self.client.track_user()

    @responses.activate
    def test_track_user(self):
        """
        Tests a successful call to /users/track.
        """
        responses.add(
            responses.POST,
            self.USERS_TRACK_URL,
            json={'message': 'success'},
            status=201
        )
        self.client.track_user(
            attributes=[{'user_aliases': [
                {
                    'external_id': '1',
                    'attribute': f'attribute-{i}'
                }
            ]} for i in range(76)],
            events=[{'events_': [
                {
                    'external_id': '1',
                    'name': f'event-{i}'
                }
            ]} for i in range(151)]
        )

        assert len(responses.calls) == 3

    @responses.activate
    def test_track_user_batching(self):
        """
        Tests that calls to /users/track are batched correctly.
        """
        responses.add(
            responses.POST,
            self.USERS_TRACK_URL,
            json={'message': 'success'},
            status=201
        )
        self.client.track_user(
            attributes=[{'user_aliases': [
                {
                    'external_id': '1',
                    'attribute': 'attribute'
                }
            ]}])

        assert len(responses.calls) == 1

    @ddt.data(
        {'emails': [], 'alias_label': 'alias_label'},
        {'emails': ['test@example.com'], 'alias_label': ''},
    )
    def test_create_braze_alias_bad_args(self, args):
        """
        Tests that arguments are validated.
        """

        with self.assertRaises(BrazeClientError):
            self.client.create_braze_alias(**args)

    @responses.activate
    def test_create_braze_alias_success(self):
        """
        Tests that calls are made to /users/alias/new and /users/track if
        a Braze user doesn't exist for the email yet.
        """
        responses.add(
            responses.POST,
            self.EXPORT_ID_URL,
            json={'users': [], 'message': 'success'},
            status=201
        )
        responses.add(
            responses.POST,
            self.NEW_ALIAS_URL,
            json={'message': 'success'},
            status=201
        )
        responses.add(
            responses.POST,
            self.USERS_TRACK_URL,
            json={'message': 'success'},
            status=201
        )

        self.client.create_braze_alias(
            emails=['test@example.com'],
            alias_label='alias_label'
        )

        assert len(responses.calls) == 3
        assert responses.calls[0].request.url == self.EXPORT_ID_URL
        assert responses.calls[1].request.url == self.NEW_ALIAS_URL
        assert responses.calls[2].request.url == self.USERS_TRACK_URL

    @responses.activate
    def test_create_braze_alias_user_exists(self):
        """
        Tests that calls to to /users/alias/new and /users/track are not made
        if a Braze user already exists for the given email.
        """
        test_email = 'test@example.com'
        existing_enternal_id = '1'
        responses.add(
            responses.POST,
            self.EXPORT_ID_URL,
            json={'users': [{'external_id': existing_enternal_id, 'email': test_email}], 'message': 'success'},
            status=201
        )
        responses.add(
            responses.POST,
            self.NEW_ALIAS_URL,
            json={'message': 'success'},
            status=201
        )
        responses.add(
            responses.POST,
            self.USERS_TRACK_URL,
            json={'message': 'success'},
            status=201
        )

        self.client.create_braze_alias(
            emails=[test_email],
            alias_label='alias_label',
            attributes=[]
        )

        assert len(responses.calls) == 3
        assert responses.calls[0].request.url == self.EXPORT_ID_URL
        assert responses.calls[1].request.url == self.NEW_ALIAS_URL
        alias_data = json.loads(responses.calls[1].request.body)
        assert alias_data['user_aliases'][0]['external_id'] == existing_enternal_id
        assert responses.calls[2].request.url == self.USERS_TRACK_URL

    @responses.activate
    def test_create_braze_alias_batching(self):
        """
        Tests that calls are made to /users/alias/new are batched correctly.
        """
        responses.add(
            responses.POST,
            self.EXPORT_ID_URL,
            json={'users': [], 'message': 'success'},
            status=201
        )
        responses.add(
            responses.POST,
            self.NEW_ALIAS_URL,
            json={'message': 'success'},
            status=201
        )
        responses.add(
            responses.POST,
            self.USERS_TRACK_URL,
            json={'message': 'success'},
            status=201
        )

        emails = [f'test-{i}@example.com' for i in range(101)]
        self.client.create_braze_alias(
            emails=emails,
            alias_label='alias_label'
        )

        create_alias_num_batches = math.ceil(len(emails) / 50)
        track_user_num_batches = math.ceil(len(emails) / 75)
        identify_users_num_batches = math.ceil(len(emails) / GET_EXTERNAL_IDS_CHUNK_SIZE)

        assert len(responses.calls) == identify_users_num_batches + create_alias_num_batches + track_user_num_batches
        export_id_calls = [call for call in responses.calls if call.request.url == self.EXPORT_ID_URL]
        new_alias_calls = [call for call in responses.calls if call.request.url == self.NEW_ALIAS_URL]
        track_user_calls = [call for call in responses.calls if call.request.url == self.USERS_TRACK_URL]
        assert len(export_id_calls) == identify_users_num_batches
        assert len(new_alias_calls) == create_alias_num_batches
        assert len(track_user_calls) == track_user_num_batches

    @ddt.data(
        {'emails': [], 'subject': 'subject', 'body': 'body', 'from_email': 'support@email.com'},
        {'emails': ['test@example.com'], 'subject': '', 'body': 'body', 'from_email': 'support@email.com'},
        {'emails': ['test@example.com'], 'subject': 'subject', 'body': '', 'from_email': 'support@email.com'},
        {'emails': [], 'subject': 'subject', 'body': 'body', 'from_email': ''},
    )
    def test_send_email_bad_args(self, args):
        """
        Tests that arguments are validated.
        """

        with self.assertRaises(BrazeClientError):
            self.client.send_email(**args)

    @responses.activate
    def test_send_email_success(self):
        """
        Tests a successful call to /campaigns/trigger/send.
        """
        responses.add(
            responses.POST,
            self.EXPORT_ID_URL,
            json={'users': [{'external_id': '1'}], 'message': 'success'},
            status=201
        )

        responses.add(
            responses.POST,
            self.MESSAGE_SEND_URL,
            json={'dispatch_id': 'dispatch_id', 'message': 'success'},
            status=201
        )

        response = self.client.send_email(
            emails=['test@example.com'],
            subject='subject',
            body='body',
            from_email='support@email.com',
        )

        self.assertEqual(response['dispatch_id'], 'dispatch_id')
        assert len(responses.calls) == 2
        assert responses.calls[0].request.url == self.EXPORT_ID_URL
        assert responses.calls[1].request.url == self.MESSAGE_SEND_URL

    @responses.activate
    def test_send_email_user_not_found(self):
        """
        Tests that an error is thrown if braze user is not found.
        """
        responses.add(
            responses.POST,
            self.EXPORT_ID_URL,
            json={'users': [], 'invalid_ids': ['1'], 'message': 'success'},
            status=201
        )

        with self.assertRaises(BrazeClientError):
            self.client.send_email(
                emails=['test@example.com'],
                subject='subject',
                body='body',
                from_email='support@email.com',
            )

    def test_send_campaign_message_bad_args(self):
        """
        Tests that arguments are validated.
        """
        with self.assertRaises(BrazeClientError):
            self.client.send_campaign_message(campaign_id='1', emails=[], recipients=[])

    @responses.activate
    def test_send_campaign_message_success(self):
        """
        Tests a successful call to /campaigns/trigger/send.
        """
        responses.add(
            responses.POST,
            self.EXPORT_ID_URL,
            json={'users': [{'external_id': '1'}], 'message': 'success'},
            status=201
        )
        responses.add(
            responses.POST,
            self.CAMPAIGN_SEND_URL,
            json={'dispatch_id': 'dispatch_id', 'message': 'success'},
            status=201
        )

        response = self.client.send_campaign_message(
            emails=['test@example.com'],
            campaign_id='campaign_id'
        )

        assert len(responses.calls) == 2
        self.assertEqual(response['dispatch_id'], 'dispatch_id')

    @responses.activate
    def test_send_campaign_message_user_not_found(self):
        """
        Tests that an error is thrown if braze user is not found.
        """
        responses.add(
            responses.POST,
            self.EXPORT_ID_URL,
            json={'users': [], 'invalid_ids': ['1'], 'message': 'success'},
            status=201
        )

        with self.assertRaises(BrazeClientError):
            self.client.send_campaign_message(
                emails=['test@example.com'],
                campaign_id='campaign_id'
            )

    def test_send_canvas_message_bad_args(self):
        """
        Tests that arguments are validated.
        """
        with self.assertRaises(BrazeClientError):
            self.client.send_canvas_message(canvas_id='1', emails=[], recipients=[])

    @responses.activate
    def test_send_canvas_message_success(self):
        """
        Tests a successful call to /canvas/trigger/send.
        """
        responses.add(
            responses.POST,
            self.CANVAS_SEND_URL,
            json={'dispatch_id': 'dispatch_id', 'message': 'success'},
            status=201
        )

        responses.add(
            responses.POST,
            self.EXPORT_ID_URL,
            json={'users': [{'external_id': '1'}], 'message': 'success'},
            status=201
        )

        response = self.client.send_canvas_message(
            emails=['test@example.com'],
            canvas_id='canvas_id'
        )

        assert len(responses.calls) == 2
        self.assertEqual(response['dispatch_id'], 'dispatch_id')

    @responses.activate
    def test_send_canvas_message_user_not_found(self):
        """
        Tests that an error is thrown if braze user is not found.
        """
        responses.add(
            responses.POST,
            self.EXPORT_ID_URL,
            json={'users': [], 'invalid_ids': ['1'], 'message': 'success'},
            status=201
        )

        with self.assertRaises(BrazeClientError):
            self.client.send_canvas_message(
                emails=['test@example.com'],
                canvas_id='canvas_id'
            )

    @responses.activate
    def test_braze_bad_request_error(self):
        """
        Tests that BrazeBadRequestError is raised if a 400 status
        code is returned.
        """
        self._mock_braze_error_response(url=self.EXPORT_ID_URL, status=400)

        with self.assertRaises(BrazeBadRequestError):
            self.client.get_braze_external_id(email='test@example.com')

        self._mock_braze_error_response(url=self.RETRIEVE_UNSUBSCRIBED_EMAILS, status=400, request_type="GET")

        with self.assertRaises(BrazeBadRequestError):
            self.client.retrieve_unsubscribed_emails(start_date='2001-01-01', end_date='2002-02-02')

    @responses.activate
    def test_braze_unauthorized_error(self):
        """
        Tests that BrazeUnauthorizedError is raised if a 401 status
        code is returned.
        """
        self._mock_braze_error_response(url=self.EXPORT_ID_URL, status=401)

        with self.assertRaises(BrazeUnauthorizedError):
            self.client.get_braze_external_id(email='test@example.com')

        self._mock_braze_error_response(url=self.RETRIEVE_UNSUBSCRIBED_EMAILS, status=401, request_type="GET")

        with self.assertRaises(BrazeUnauthorizedError):
            self.client.retrieve_unsubscribed_emails(start_date='2001-01-01', end_date='2002-02-02')

    @responses.activate
    def test_braze_forbidden_error(self):
        """
        Tests that BrazeForbiddenError is raised if a 403 status
        code is returned.
        """
        self._mock_braze_error_response(url=self.EXPORT_ID_URL, status=403)

        with self.assertRaises(BrazeForbiddenError):
            self.client.get_braze_external_id(email='test@example.com')

        self._mock_braze_error_response(url=self.RETRIEVE_UNSUBSCRIBED_EMAILS, status=403, request_type="GET")

        with self.assertRaises(BrazeForbiddenError):
            self.client.retrieve_unsubscribed_emails(start_date='2001-01-01', end_date='2002-02-02')

    @responses.activate
    def test_braze_not_found_error(self):
        """
        Tests that BrazeNotFoundError is raised if a 404 status
        code is returned.
        """
        self._mock_braze_error_response(url=self.EXPORT_ID_URL, status=404)

        with self.assertRaises(BrazeNotFoundError):
            self.client.get_braze_external_id(email='test@example.com')

        self._mock_braze_error_response(url=self.RETRIEVE_UNSUBSCRIBED_EMAILS, status=404, request_type="GET")

        with self.assertRaises(BrazeNotFoundError):
            self.client.retrieve_unsubscribed_emails(start_date='2001-01-01', end_date='2002-02-02')

    @responses.activate
    def test_braze_rate_limit_error(self):
        """
        Tests that BrazeRateLimitError is raised if a 429 status
        code is returned.
        """
        rate_limit_reset = "1648585423"
        self._mock_braze_error_response(
            status=429,
            url=self.EXPORT_ID_URL,
            headers={"X-RateLimit-Reset": rate_limit_reset}
        )

        with self.assertRaises(BrazeRateLimitError) as exception_context_manager:
            self.client.get_braze_external_id(email='test@example.com')

        assert exception_context_manager.exception.reset_epoch_s == float(rate_limit_reset)

        self._mock_braze_error_response(
            status=429,
            url=self.RETRIEVE_UNSUBSCRIBED_EMAILS,
            headers={"X-RateLimit-Reset": rate_limit_reset},
            request_type="GET"
        )

        with self.assertRaises(BrazeRateLimitError) as exception_context_manager:
            self.client.retrieve_unsubscribed_emails(start_date='2001-01-01', end_date='2002-02-02')

        assert exception_context_manager.exception.reset_epoch_s == float(rate_limit_reset)

    @responses.activate
    def test_braze_internal_server_error(self):
        """
        Tests that a BrazeInternalServerError is raised if a 5xx
        status code is returned.
        """
        self._mock_braze_error_response(
            status=500,
            url=self.EXPORT_ID_URL,
        )
        with self.assertRaises(BrazeInternalServerError):
            self.client.get_braze_external_id(email='test@example.com')

        self._mock_braze_error_response(
            status=500,
            url=self.RETRIEVE_UNSUBSCRIBED_EMAILS,
            request_type="GET"
        )
        with self.assertRaises(BrazeInternalServerError):
            self.client.retrieve_unsubscribed_emails(start_date='2001-01-01', end_date='2002-02-02')

    @responses.activate
    def test_braze_client_error(self):
        """
        Tests that a generic BrazeClientError is raised.
        """
        self._mock_braze_error_response(
            status=410,
            url=self.EXPORT_ID_URL,
        )
        with self.assertRaises(BrazeClientError):
            self.client.get_braze_external_id(email='test@example.com')

        self._mock_braze_error_response(
            status=410,
            url=self.RETRIEVE_UNSUBSCRIBED_EMAILS,
            request_type="GET"
        )
        with self.assertRaises(BrazeClientError):
            self.client.retrieve_unsubscribed_emails(start_date='2001-01-01', end_date='2002-02-02')

    def test_unsubscribe_user_email_bad_args_empty_email(self):
        """
        Tests that arguments are validated.
        """
        with self.assertRaises(BrazeClientError):
            self.client.unsubscribe_user_email(email=[])

    def test_unsubscribe_user_email_bad_args_long_email_length(self):
        """
        Tests that arguments are validated.
        """
        emails = ['test@example.com'] * 51
        with self.assertRaises(BrazeClientError):
            self.client.unsubscribe_user_email(email=emails)

    @responses.activate
    def test_unsubscribe_user_email_success(self):
        """
        Tests a successful call to the /email/status endpoint.
        """
        responses.add(
            responses.POST,
            self.UNSUBSCRIBE_USER_EMAIL_URL,
            json={'message': 'success'},
            status=201
        )
        response = self.client.unsubscribe_user_email(email='test@example.com')

        self.assertEqual(response, {'message': 'success'})
        assert len(responses.calls) == 1
        assert responses.calls[0].request.url == self.UNSUBSCRIBE_USER_EMAIL_URL

    def _generate_retrieve_unsubscribed_emails_url(
            self,
            start_date,
            end_date,
            limit=None,
            offset=None,

    ):
        """
        Generate the retrieve unsubscribed emails URL with query params
        """
        params = {
            'start_date': start_date,
            'end_date': end_date,
            'limit': str(limit) if limit else str(UNSUBSCRIBED_EMAILS_API_LIMIT),
            'offset': str(offset) if offset else '0',
            'sort_direction': UNSUBSCRIBED_EMAILS_API_SORT_DIRECTION,
        }

        url = (
            f"{self.RETRIEVE_UNSUBSCRIBED_EMAILS}?"
            f"start_date={params['start_date']}&"
            f"end_date={params['end_date']}&"
            f"limit={params['limit']}&"
            f"offset={params['offset']}&"
            f"sort_direction={params['sort_direction']}"
        )
        return params, url

    @responses.activate
    def test_retrieve_unsubscribed_emails_success(self):
        mock_response = {
            'emails': ['test1@example.com', 'test2@example.com']
        }
        params, url = self._generate_retrieve_unsubscribed_emails_url(
            self.start_date,
            self.end_date,
        )
        responses.add(
            responses.GET,
            url,
            json=mock_response,
            status=200
        )

        result = self.client.retrieve_unsubscribed_emails(self.start_date, self.end_date)

        self.assertEqual(result, ['test1@example.com', 'test2@example.com'])

        request = responses.calls[0].request
        self.assertEqual(request.url, url)
        self.assertEqual(request.params, params)

    @responses.activate
    def test_retrieve_unsubscribed_emails_invalid_dates(self):
        with self.assertRaises(BrazeClientError):
            self.client.retrieve_unsubscribed_emails(self.end_date, self.start_date)

        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_retrieve_unsubscribed_emails_invalid_date_format(self):
        with self.assertRaises(BrazeClientError):
            self.client.retrieve_unsubscribed_emails('01/01/2001', '02/02/2002')

        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_retrieve_unsubscribed_emails_empty_response(self):
        mock_response = {
            'emails': []
        }

        params, url = self._generate_retrieve_unsubscribed_emails_url(
            self.start_date,
            self.end_date,
        )

        responses.add(
            responses.GET,
            url,
            json=mock_response,
            status=200
        )

        result = self.client.retrieve_unsubscribed_emails(self.start_date, self.end_date)

        self.assertEqual(result, [])

        request = responses.calls[0].request
        self.assertEqual(request.url, url)
        self.assertEqual(request.params, params)

    @responses.activate
    def test_retrieve_unsubscribed_emails_multiple_api_calls(self):
        mock_response_1 = {
            "emails": ["test@example.com"] * 500,
        }
        mock_response_2 = {
            "emails": ["test@example.com"] * 500,
        }
        mock_response_3 = {
            "emails": ["test@example.com"] * 100,
        }

        params_1, url_1 = self._generate_retrieve_unsubscribed_emails_url(
            self.start_date,
            self.end_date,
            UNSUBSCRIBED_EMAILS_API_LIMIT,
            0
        )

        params_2, url_2 = self._generate_retrieve_unsubscribed_emails_url(
            self.start_date,
            self.end_date,
            UNSUBSCRIBED_EMAILS_API_LIMIT,
            UNSUBSCRIBED_EMAILS_API_LIMIT
        )

        params_3, url_3 = self._generate_retrieve_unsubscribed_emails_url(
            self.start_date,
            self.end_date,
            UNSUBSCRIBED_EMAILS_API_LIMIT,
            UNSUBSCRIBED_EMAILS_API_LIMIT * 2
        )

        responses.add(
            responses.GET,
            url_1,
            json=mock_response_1,
            status=200
        )
        responses.add(
            responses.GET,
            url_2,
            json=mock_response_2,
            status=200
        )
        responses.add(
            responses.GET,
            url_3,
            json=mock_response_3,
            status=200
        )

        result = self.client.retrieve_unsubscribed_emails(self.start_date, self.end_date)
        expected_result = ["test@example.com"] * 1100
        self.assertEqual(result, expected_result)

        expected_calls = responses.calls
        self.assertEqual(len(expected_calls), 3)
        self.assertDictEqual(expected_calls[0].request.params, params_1)
        self.assertDictEqual(expected_calls[1].request.params, params_2)
        self.assertDictEqual(expected_calls[2].request.params, params_3)
        self.assertEqual(expected_calls[0].request.url, url_1)
        self.assertEqual(expected_calls[1].request.url, url_2)
        self.assertEqual(expected_calls[2].request.url, url_3)
