"""
Braze API Client.
"""

import json
from collections import deque
from urllib.parse import urljoin

import requests

from braze.constants import TRACK_USER_COMPONENT_CHUNK_SIZE, USER_ALIAS_CHUNK_SIZE, BrazeAPIEndpoints

from .exceptions import (
    BrazeBadRequestError,
    BrazeClientError,
    BrazeForbiddenError,
    BrazeInternalServerError,
    BrazeNotFoundError,
    BrazeRateLimitError,
    BrazeUnauthorizedError,
)


class BrazeClient:
    """
    Client for Braze REST API.
    """

    def __init__(
            self,
            api_key,
            api_url,
            app_id
    ):
        """
        Initialize the Braze Client with configuration values.
        """
        self.api_key = api_key
        self.api_url = api_url
        self.app_id = app_id
        self.session = requests.Session()

    def _chunks(self, a_list, chunk_size):
        """
        Break a list up into chunks.
        """
        for i in range(0, len(a_list), chunk_size):
            yield a_list[i:i + chunk_size]

    def _post_request(self, body, endpoint):
        """
        Http posts the message body with associated headers.

        Arguments:
            body (dict): The request body
            endpoint (str): The endpoint for the API e.g. /messages/send
        Returns:
            resp (json): The http response in json format
        Raises:
            BrazeClientError: If a failure message is returned
            BrazeBadRequestError: If a 400 status code is returned
            BrazeUnauthorizedError: If a 401 status code is returned
            BrazeUnauthorizedError: If a 403 status code is returned
            BrazeNotFoundError: If a 404 status code is returned
            BrazeRateLimitError: If a 429 status code is returned
            BrazeInternalServerError: If a 5XX status code is returned
        """
        self.session.headers.update(
            {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        )

        resp = self.session.post(urljoin(self.api_url, endpoint), data=json.dumps(body), timeout=2)

        try:
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as exc:
            # https://www.braze.com/docs/api/errors/#fatal-errors
            status_code = exc.response.status_code

            if status_code == 400:
                raise BrazeBadRequestError from exc

            if status_code == 401:
                raise BrazeUnauthorizedError from exc

            if status_code == 403:
                raise BrazeForbiddenError from exc

            if status_code == 404:
                raise BrazeNotFoundError from exc

            if status_code == 429:
                headers = exc.response.headers
                # https://www.braze.com/docs/api/basics/#api-limits
                reset_epoch_s = float(headers.get("X-RateLimit-Reset", "0"))
                raise BrazeRateLimitError(reset_epoch_s) from exc

            if str(status_code).startswith('5'):
                raise BrazeInternalServerError from exc

            raise BrazeClientError from exc

    def get_braze_external_id(self, email):
        """
        Check via /users/export/ids if the user account exists in Braze.

        https://www.braze.com/docs/api/endpoints/export/user_data/post_users_identifier/

        Arguments:
            email (str): e.g. 'test1@example.com'
        Returns:
            external_id (int): external_id if account exists
        """
        payload = {
            'email_address': email,
            'fields_to_export': ['external_id']
        }
        response = self._post_request(payload, BrazeAPIEndpoints.EXPORT_IDS)
        if response['users'] and 'external_id' in response['users'][0]:
            return response['users'][0]['external_id']

        return None

    def identify_users(self, aliases_to_identify):
        """
        Identify unidentified (alias-only) users.

        https://www.braze.com/docs/api/endpoints/user_data/post_user_identify/

        Arguments:
            aliases_to_identify (list of dicts): The list of aliases to identify in the format of
            {
                'external_id': 'external_identifier',
                'user_alias' : { 'alias_label' : 'example_label', 'alias_name' : 'example_alias' }
            }
        """
        if not aliases_to_identify:
            msg = 'Bad arguments, aliases_to_identify is required.'
            raise BrazeClientError(msg)

        payload = {
            'aliases_to_identify': aliases_to_identify
        }

        return self._post_request(payload, BrazeAPIEndpoints.IDENTIFY_USERS)

    def track_user(
        self,
        attributes=None,
        events=None,
        purchases=None
    ):
        """
        Record custom events, purchases, and update user profile attributes.

        https://www.braze.com/docs/api/endpoints/user_data/post_user_track/

        Arguments:
            attributes (list): The list of attribute objects
            events (list): The list of event objects
            purchases (list): The list of purchases objects
        """
        payload = {}
        if not (attributes or events or purchases):
            msg = 'Bad arguments, please check that attributes, events, or purchases are non-empty.'
            raise BrazeClientError(msg)

        attributes = attributes or []
        events = events or []
        purchases = purchases or []

        # Each request can contain up to 75 events, 75 attribute updates,
        # and 75 purchases (255 total).
        attribute_chunks = deque(self._chunks(attributes, TRACK_USER_COMPONENT_CHUNK_SIZE))
        events_chunks = deque(self._chunks(events, TRACK_USER_COMPONENT_CHUNK_SIZE))
        purchase_chunks = deque(self._chunks(purchases, TRACK_USER_COMPONENT_CHUNK_SIZE))

        while attribute_chunks or events_chunks or purchase_chunks:
            payload = {}

            if attribute_chunks:
                payload['attributes'] = attribute_chunks.popleft()

            if events:
                payload['events'] = events_chunks.popleft()

            if purchases:
                payload['purchases'] = purchase_chunks.popleft()

            self._post_request(payload, BrazeAPIEndpoints.TRACK_USER)

    def create_braze_alias(self, emails, alias_label, attributes=None):
        """
        Create a Braze anonymous user for each email and assign it an alias.

        https://www.braze.com/docs/api/endpoints/user_data/post_user_alias/

        Arguments:
            emails (list): e.g. ['test1@example.com', 'test2@example.com']
            alias_label (str): The type of alias
            attributes (list): The list of attributes to add to the user
        """
        if not (emails and alias_label):
            msg = 'Bad arguments, please check that emails, and alias_label are non-empty.'
            raise BrazeClientError(msg)

        user_aliases = []
        attributes = attributes or []

        for email in emails:
            if not self.get_braze_external_id(email):
                user_alias = {
                    'alias_label': alias_label,
                    'alias_name': email,
                }
                user_aliases.append(user_alias)
                attribute = {
                    'user_alias': user_alias,
                    'email': email,
                }
                attributes.append(attribute)

        # Each request can support up to 50 aliases.
        for user_alias_chunk in self._chunks(user_aliases, USER_ALIAS_CHUNK_SIZE):
            alias_payload = {
                'user_aliases': user_alias_chunk,
            }
            self._post_request(alias_payload, BrazeAPIEndpoints.NEW_ALIAS)

        if attributes:
            self.track_user(attributes=attributes)

    def send_email(
        self,
        emails,
        subject,
        body,
        from_email,
        campaign_id=None,
        recipient_subscription_state='all',
        reply_to=None,
        attachments=None,
        override_frequency_capping=False
    ):
        """
        Send an email via Braze Rest API.

        Arguments:
            emails (list): e.g. ['test1@example.com', 'test2@example.com']
            subject (str): e.g. 'Test Subject'
            body (str): e.g. '<html>Test Html Message</html>'
            from_email (str): Sender for the email
            campaign_id (str): The campaign identifier used to
            track campaign stats
            recipient_subscription_state (str): Subscription state of the users
            reply_to (str): Reply to address for email replies
            attachments (list): List of dicts with filename and url keys
            override_frequency_capping (bool): ignore frequency_capping for campaigns, defaults to False
        Returns:
            response (dict): The response object
        """
        if not (emails and subject and body and from_email):
            msg = 'Bad arguments, please check that emails, subject, body, and from_email are non-empty.'
            raise BrazeClientError(msg)

        external_ids = []
        for email in emails:
            external_id = self.get_braze_external_id(email)
            if not external_id:
                raise BrazeClientError(f'Braze user with email {email} was not found.')

            external_ids.append(str(external_id))

        email = {
            'app_id': self.app_id,
            'subject': subject,
            'from': from_email,
            'body': body,
        }

        if attachments:
            email['attachments'] = attachments
        if reply_to:
            email['reply_to'] = reply_to

        payload = {
            'external_user_ids': external_ids,
            'recipient_subscription_state': recipient_subscription_state,
            'messages': {
                'email': email
            },
            'campaign_id': campaign_id,
            'override_frequency_capping': override_frequency_capping
        }
        return self._post_request(payload, BrazeAPIEndpoints.SEND_MESSAGE)

    def send_campaign_message(
        self,
        campaign_id,
        emails=None,
        recipients=None,
        trigger_properties=None,
    ):
        """
        Send a campaign message via API-triggered delivery.

        https://www.braze.com/docs/api/endpoints/messaging/send_messages/post_send_triggered_campaigns/

        Arguments:
            campaign_id (dict): The campaign identifier, the campaign must
            be an API-triggered campaign (set up via delivery settings)
            emails (list): e.g. ['test1@example.com', 'test2@example.com']
            recipients (list): The recipients objects
            trigger_properties: Personalization key-value pairs that will
            apply to all users
        Returns:
            response (dict): The response object
        """
        if not (emails or recipients):
            msg = 'Bad arguments, please check that emails or recipients are non-empty.'
            raise BrazeClientError(msg)

        emails = emails or []
        recipients = recipients or []

        message = {
            'campaign_id': campaign_id,
            'trigger_properties': trigger_properties or {},
            'recipients': recipients,
            'broadcast': False
        }

        for email in emails:
            external_user_id = self.get_braze_external_id(email)

            recipient = {
                'external_user_id': external_user_id,
            }

            if not external_user_id:
                raise BrazeClientError(
                    f'Braze user with email {email} was not found. Please pass in custom recipients '
                    'if you wish to send campaign messages to anonymous users.'
                )

            recipients.append(recipient)

        return self._post_request(message, BrazeAPIEndpoints.SEND_CAMPAIGN)
