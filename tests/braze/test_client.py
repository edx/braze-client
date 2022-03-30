"""
Tests for Braze client.
"""

import math
from unittest import TestCase

import ddt
import responses

from braze.client import BrazeClient
from braze.constants import BrazeAPIEndpoints
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
    EXPORT_ID_URL = BRAZE_URL + BrazeAPIEndpoints.EXPORT_IDS
    NEW_ALIAS_URL = BRAZE_URL + BrazeAPIEndpoints.NEW_ALIAS
    USERS_TRACK_URL = BRAZE_URL + BrazeAPIEndpoints.TRACK_USER
    MESSAGE_SEND_URL = BRAZE_URL + BrazeAPIEndpoints.SEND_MESSAGE
    CAMPAIGN_SEND_URL = BRAZE_URL + BrazeAPIEndpoints.SEND_CAMPAIGN

    def _get_braze_client(self):
        return BrazeClient(
            api_key='api_key',
            api_url='http://braze-api-url.com',
            app_id='app_id'
        )

    def _mock_braze_error_response(self, status, headers=None, url=EXPORT_ID_URL):
        responses.add(
            responses.POST,
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
        client = self._get_braze_client()
        external_id = client.get_braze_external_id(email='test@example.com')

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
        client = self._get_braze_client()
        external_id = client.get_braze_external_id(email='test@example.com')

        assert external_id is None
        assert len(responses.calls) == 1
        assert responses.calls[0].request.url == self.EXPORT_ID_URL

    def test_track_user_bad_args(self):
        """
        Tests that arguments are validated.
        """
        client = self._get_braze_client()

        with self.assertRaises(BrazeClientError):
            client.track_user()

    @responses.activate
    def test_track_user(self):
        """
        Tests a successful call to /users/track.
        """
        client = self._get_braze_client()

        responses.add(
            responses.POST,
            self.USERS_TRACK_URL,
            json={'message': 'success'},
            status=201
        )
        client = self._get_braze_client()
        client.track_user(
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
        client = self._get_braze_client()

        responses.add(
            responses.POST,
            self.USERS_TRACK_URL,
            json={'message': 'success'},
            status=201
        )
        client = self._get_braze_client()
        client.track_user(
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
        client = self._get_braze_client()

        with self.assertRaises(BrazeClientError):
            client.create_braze_alias(**args)

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
        client = self._get_braze_client()

        client.create_braze_alias(
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
        responses.add(
            responses.POST,
            self.EXPORT_ID_URL,
            json={'users': [{'external_id': '1'}], 'message': 'success'},
            status=201
        )

        client = self._get_braze_client()
        client.create_braze_alias(
            emails=['test@example.com'],
            alias_label='alias_label',
            attributes=[]
        )

        assert len(responses.calls) == 1
        assert responses.calls[0].request.url == self.EXPORT_ID_URL

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
        client = self._get_braze_client()

        emails = [f'test-{i}@example.com' for i in range(101)]
        client.create_braze_alias(
            emails=emails,
            alias_label='alias_label'
        )

        create_alias_batch_size = math.ceil(len(emails) / 50)
        track_user_batch_size = math.ceil(len(emails) / 75)

        assert len(responses.calls) == len(emails) + create_alias_batch_size + track_user_batch_size
        export_id_calls = [call for call in responses.calls if call.request.url == self.EXPORT_ID_URL]
        new_alias_calls = [call for call in responses.calls if call.request.url == self.NEW_ALIAS_URL]
        track_user_calls = [call for call in responses.calls if call.request.url == self.USERS_TRACK_URL]
        assert len(export_id_calls) == len(emails)
        assert len(new_alias_calls) == create_alias_batch_size
        assert len(track_user_calls) == track_user_batch_size

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
        client = self._get_braze_client()

        with self.assertRaises(BrazeClientError):
            client.send_email(**args)

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

        client = self._get_braze_client()
        response = client.send_email(
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

        client = self._get_braze_client()

        with self.assertRaises(BrazeClientError):
            client = self._get_braze_client()
            client.send_email(
                emails=['test@example.com'],
                subject='subject',
                body='body',
                from_email='support@email.com',
            )

    def test_send_campaign_message_bad_args(self):
        """
        Tests that arguments are validated.
        """
        client = self._get_braze_client()
        with self.assertRaises(BrazeClientError):
            client.send_campaign_message(campaign_id='1', emails=[], recipients=[])

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

        client = self._get_braze_client()
        response = client.send_campaign_message(
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

        client = self._get_braze_client()

        with self.assertRaises(BrazeClientError):
            client = self._get_braze_client()
            client.send_campaign_message(
                emails=['test@example.com'],
                campaign_id='campaign_id'
            )

    @responses.activate
    def test_braze_bad_request_error(self):
        """
        Tests that BrazeBadRequestError is raised if a 400 status
        code is returned.
        """
        self._mock_braze_error_response(url=self.EXPORT_ID_URL, status=400)

        with self.assertRaises(BrazeBadRequestError):
            client = self._get_braze_client()
            client.get_braze_external_id(email='test@example.com')

    @responses.activate
    def test_braze_unathorized_error(self):
        """
        Tests that BrazeUnauthorizedError is raised if a 401 status
        code is returned.
        """
        self._mock_braze_error_response(url=self.EXPORT_ID_URL, status=401)

        with self.assertRaises(BrazeUnauthorizedError):
            client = self._get_braze_client()
            client.get_braze_external_id(email='test@example.com')

    @responses.activate
    def test_braze_forbidden_error(self):
        """
        Tests that BrazeUnauthorizedError is raised if a 403 status
        code is returned.
        """
        self._mock_braze_error_response(url=self.EXPORT_ID_URL, status=403)

        with self.assertRaises(BrazeForbiddenError):
            client = self._get_braze_client()
            client.get_braze_external_id(email='test@example.com')

    @responses.activate
    def test_braze_not_found_error(self):
        """
        Tests that BrazeNotFoundError is raised if a 404 status
        code is returned.
        """
        self._mock_braze_error_response(url=self.EXPORT_ID_URL, status=404)

        with self.assertRaises(BrazeNotFoundError):
            client = self._get_braze_client()
            client.get_braze_external_id(email='test@example.com')

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
            client = self._get_braze_client()
            client.get_braze_external_id(email='test@example.com')

        assert exception_context_manager.exception.reset_epoch_s == float(rate_limit_reset)

    @responses.activate
    def test_braze_internal_server_error(self):
        """
        Tests that a BrazeInternalServerError is raised if a 5xx
        status code is returned.
        """
        responses.add(
            responses.POST,
            self.EXPORT_ID_URL,
            status=500
        )
        with self.assertRaises(BrazeInternalServerError):
            client = self._get_braze_client()
            client.get_braze_external_id(email='test@example.com')
