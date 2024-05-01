"""
Braze API Client.
"""
import datetime
import json
import logging
from collections import deque
from urllib.parse import urljoin

import requests

from braze.constants import (
    GET_EXTERNAL_IDS_CHUNK_SIZE,
    MAX_NUM_IDENTIFY_USERS_ALIASES,
    REQUEST_TYPE_GET,
    REQUEST_TYPE_POST,
    TRACK_USER_COMPONENT_CHUNK_SIZE,
    UNSUBSCRIBED_EMAILS_API_LIMIT,
    UNSUBSCRIBED_EMAILS_API_SORT_DIRECTION,
    UNSUBSCRIBED_STATE,
    USER_ALIAS_CHUNK_SIZE,
    BrazeAPIEndpoints,
)

from .exceptions import (
    BrazeBadRequestError,
    BrazeClientError,
    BrazeForbiddenError,
    BrazeInternalServerError,
    BrazeNotFoundError,
    BrazeRateLimitError,
    BrazeUnauthorizedError,
)

logger = logging.getLogger(__name__)


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

    def _make_request(self, data, endpoint, request_type):
        """
        Http posts the message body with associated headers.

        Arguments:
            data (dict): The request body for post request or params for get request
            endpoint (str): The endpoint for the API e.g. /messages/send
            request_type (str): The request_type for the API e.g. 'post or 'get'
        Returns:
            resp (json): The http response in json format
        Raises:
            BrazeClientError: If a failure message is returned
            BrazeBadRequestError: If a 400 status code is returned
            BrazeUnauthorizedError: If a 401 status code is returned
            BrazeForbiddenError: If a 403 status code is returned
            BrazeNotFoundError: If a 404 status code is returned
            BrazeRateLimitError: If a 429 status code is returned
            BrazeInternalServerError: If a 5XX status code is returned
        """
        self.session.headers.update(
            {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        )

        if request_type == 'post':
            resp = self.session.post(urljoin(self.api_url, endpoint), data=json.dumps(data), timeout=2)
        else:
            resp = self.session.get(urljoin(self.api_url, endpoint), params=data, timeout=2)

        try:
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as exc:
            # https://www.braze.com/docs/api/errors/#fatal-errors
            status_code = exc.response.status_code
            response_content = exc.response.text

            if status_code == 400:
                raise BrazeBadRequestError(response_content) from exc

            if status_code == 401:
                raise BrazeUnauthorizedError(response_content) from exc

            if status_code == 403:
                raise BrazeForbiddenError(response_content) from exc

            if status_code == 404:
                raise BrazeNotFoundError(response_content) from exc

            if status_code == 429:
                headers = exc.response.headers
                # https://www.braze.com/docs/api/basics/#api-limits
                reset_epoch_s = float(headers.get("X-RateLimit-Reset", "0"))
                raise BrazeRateLimitError(reset_epoch_s) from exc

            if str(status_code).startswith('5'):
                raise BrazeInternalServerError(response_content) from exc

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
        response = self._make_request(payload, BrazeAPIEndpoints.EXPORT_IDS, REQUEST_TYPE_POST)
        if response['users'] and 'external_id' in response['users'][0]:
            return response['users'][0].get('external_id')

        return None

    def get_braze_external_id_batch(self, emails, alias_label):
        """
        Check via /users/export/ids if the provided emails have external ids defined in Braze,
        associated with the account via an alias.

        https://www.braze.com/docs/api/endpoints/export/user_data/post_users_identifier/
        "Up to 50 external_ids or user_aliases can be included in a single request.
        Should you want to specify device_id or email_address
        only one of either identifier can be included per request.
        [...]
        if a field is missing from the object it should be assumed to be null, false, or empty
        "

        Arguments:
            emails (list(str)): e.g. ['test1@example.com', 'test1@example.com']
            alias_label (str): e.g. "my-business-segment-label"
        Returns:
            external_id (dict(str -> str): external_ids (string of lms_user_id) by email,
              for any existing external ids.
        """
        external_ids_by_email = {}
        for email_batch in self._chunks(emails, GET_EXTERNAL_IDS_CHUNK_SIZE):
            user_aliases = [
                {
                    'alias_label': alias_label,
                    'alias_name': email,
                }
                for email in email_batch
            ]
            payload = {
                'user_aliases': user_aliases,
                'fields_to_export': ['external_id', 'email']
            }
            logger.info('batch identify braze users request payload: %s', payload)

            response = self._make_request(payload, BrazeAPIEndpoints.EXPORT_IDS, REQUEST_TYPE_POST)

            for identified_user in response['users']:
                identified_email = identified_user.get('email')
                external_id = identified_user.get('external_id')
                if identified_email and external_id:
                    external_ids_by_email[identified_email] = external_id

        logger.info(f'external ids from batch identify braze users response: {external_ids_by_email}')
        return external_ids_by_email

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

        return self._make_request(payload, BrazeAPIEndpoints.IDENTIFY_USERS, REQUEST_TYPE_POST)

    def create_recipients(self, alias_label, user_id_by_email, trigger_properties_by_email=None):
        """
        Create a recipient object using the dictionary, `user_id_by_email`
        containing the user_email key and `lms_user_id` value.
        Identifies a list of given email addresess with any existing Braze alias records
        via the provided ``lms_user_id``.

        https://www.braze.com/docs/api/objects_filters/user_alias_object
        The user_alias objects requires a passed in alias_label.

        https://www.braze.com/docs/api/endpoints/user_data/post_user_identify/
        The maximum email/user_id dictionary limit is 50, any length beyond 50 will raise an error.

        The trigger properties default to None and return as an empty dictionary if no individualized
        trigger property is set based on the email.

        Arguments:
        - `alias_label` (str): The alias label of the user
        - `user_id_by_email` (dict):  A dictionary where the key is the user's email (str)
                                    and the value is the `lms_user_id` (int).
        - `trigger_properties_by_email` (dict) : A dictionary where the key is the user's email (str)
                                                and the value are the `trigger_properties` (dict)
                                                Default is None

        Raises:
        - `BrazeClientError`: if the number of entries in `user_id_by_email` exceeds 50.

        Returns:
        - Dict: A dictionary where the key is the `user_email` (str) and the value is the metadata
                relating to the braze recipient.

        Example: create_recipients(
                    'alias_label'='Enterprise',
                    'user_id_by_email'= {
                        'hamzah@example.com': 123,
                        'alex@example.com': 231,
                    },
                    'trigger_properties_by_email'= {
                        'hamzah@example.com': {
                            'foo':'bar'
                        },
                        'alex@example.com': {}
                    },
                )
        """
        if len(user_id_by_email) > MAX_NUM_IDENTIFY_USERS_ALIASES:
            msg = "Max recipient limit reached."
            raise BrazeClientError(msg)

        if trigger_properties_by_email is None:
            trigger_properties_by_email = {}

        user_aliases_by_email = {
                email: {
                    "alias_label": alias_label,
                    "alias_name": email,
                }
                for email in user_id_by_email
        }
        # Identify the user alias in case it already exists. This is necessary so
        # we don't accidently create a duplicate Braze profile.
        self.identify_users([
            {
                'external_id': lms_user_id,
                'user_alias': user_aliases_by_email.get(email)
            }
            for email, lms_user_id in user_id_by_email.items()
        ])

        attributes_by_email = {
            email: {
                "user_alias": user_aliases_by_email.get(email),
                "email": email,
                "is_enterprise_learner": True,
                "_update_existing_only": False,
            }
            for email in user_id_by_email
        }

        return {
            email: {
                'external_user_id': lms_user_id,
                'attributes': attributes_by_email.get(email),
                # If a profile does not already exist, Braze will create a new profile before sending a message.
                'send_to_existing_only': False,
                'trigger_properties': trigger_properties_by_email.get(email, {}),
            }
            for email, lms_user_id in user_id_by_email.items()
        }

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

            self._make_request(payload, BrazeAPIEndpoints.TRACK_USER, REQUEST_TYPE_POST)

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

        external_ids_by_email = self.get_braze_external_id_batch(emails, alias_label)
        for email in emails:
            user_alias = {
                'alias_label': alias_label,
                'alias_name': email,
            }
            braze_external_id = external_ids_by_email.get(email)
            # Adding a user alias for an existing user requires an external_id to be
            # included in the new user alias object.
            # http://web.archive.org/web/20231005191135/https://www.braze.com/docs/api/endpoints/user_data/post_user_alias#response
            if braze_external_id:
                user_alias['external_id'] = braze_external_id
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
            self._make_request(alias_payload, BrazeAPIEndpoints.NEW_ALIAS, REQUEST_TYPE_POST)

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
        return self._make_request(payload, BrazeAPIEndpoints.SEND_MESSAGE, REQUEST_TYPE_POST)

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
            campaign_id (str): The campaign identifier, the campaign must
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

        return self._make_request(message, BrazeAPIEndpoints.SEND_CAMPAIGN, REQUEST_TYPE_POST)

    def send_canvas_message(
        self,
        canvas_id,
        emails=None,
        recipients=None,
        canvas_entry_properties=None,
    ):
        """
        Send a canvas message via API-triggered delivery.

        https://www.braze.com/docs/api/endpoints/messaging/send_messages/post_send_triggered_canvases/

        Arguments:
            canvas_id (str): The canvas identifier, the canvas must
            be an API-triggered campaign (set up via delivery settings)
            emails (list): e.g. ['test1@example.com', 'test2@example.com']
            recipients (list): The recipients objects
            canvas_entry_properties: Personalization key-value pairs that will
            apply to all users
        Returns:
            response (dict): The response object
        """
        if not (emails or recipients):
            msg = 'Bad arguments, please check that emails or recipients are non-empty.'
            raise BrazeClientError(msg)

        emails = emails or []
        recipients = recipients or []

        for email in emails:
            external_user_id = self.get_braze_external_id(email)

            recipient = {
                'external_user_id': external_user_id,
            }

            if not external_user_id:
                raise BrazeClientError(
                    f'Braze user with email {email} was not found. Please pass in custom recipients '
                    f'if you wish to send campaign messages to anonymous users.'
                )

            recipients.append(recipient)

        message = {
            'canvas_id': canvas_id,
            'canvas_entry_properties': canvas_entry_properties or {},
            'recipients': recipients,
            'broadcast': False
        }

        return self._make_request(message, BrazeAPIEndpoints.SEND_CANVAS, REQUEST_TYPE_POST)

    def unsubscribe_user_email(
        self,
        email
    ):
        """
        Unsubscribe user's email via API.

        https://www.braze.com/docs/api/endpoints/email/post_email_subscription_status/

        Arguments:
            email (str, list): The maximum number of emails in a list can be 50 or just one str
            e.g. 'test1@example.com' or ['test2@example.com', 'test3@example.com', ...]
        Returns:
            response (dict): The response object
        """
        if not email:
            msg = 'Bad arguments, please check that emails are non-empty.'
            raise BrazeClientError(msg)

        if isinstance(email, list) and len(email) > 50:
            msg = 'Bad arguments, The maximum number of emails in a list can be 50.'
            raise BrazeClientError(msg)

        payload = {
            'email': email,
            'subscription_state': UNSUBSCRIBED_STATE
        }

        return self._make_request(payload, BrazeAPIEndpoints.UNSUBSCRIBE_USER_EMAIL, REQUEST_TYPE_POST)

    def retrieve_unsubscribed_emails(
        self,
        start_date,
        end_date,
    ):
        """
        Retrieve unsubscribe users email via API.

        https://www.braze.com/docs/api/endpoints/email/get_query_unsubscribed_email_addresses/

        Arguments:
            start_date(str): Start date of the range to retrieve unsubscribes, must be earlier than end_date.
            This is treated as midnight in UTC time by the API. Format: YYYY-MM-DD
            end_date(str): End date of the range to retrieve unsubscribes. This is treated as midnight in
            UTC time by the API. Format: YYYY-MM-DD
        Returns:
            response (list): list of emails
        """
        try:
            start_datetime = datetime.datetime.strptime(start_date, "%Y-%m-%d")
            end_datetime = datetime.datetime.strptime(end_date, "%Y-%m-%d")
            if start_datetime > end_datetime:
                raise BrazeClientError("Invalid dates: The start date must be before the end date.")
        except ValueError as exc:
            raise BrazeClientError("Invalid date format: Please provide dates in YYYY-MM-DD format.") from exc

        params = {
            'start_date': start_date,
            'end_date': end_date,
            'limit': UNSUBSCRIBED_EMAILS_API_LIMIT,
            'offset': 0,
            'sort_direction': UNSUBSCRIBED_EMAILS_API_SORT_DIRECTION,
        }

        unsubscribed_emails = []
        response = self._make_request(params, BrazeAPIEndpoints.UNSUBSCRIBED_EMAILS, REQUEST_TYPE_GET)
        emails = response.get('emails', [])
        unsubscribed_emails.extend(emails)

        # NOTE: If your date range has more than limit number of unsubscribes, you will need to make multiple API calls,
        # each time increasing the offset until a call returns either fewer than limit or zero results.
        while len(emails) >= UNSUBSCRIBED_EMAILS_API_LIMIT:
            # Update the offset for the next API call
            params['offset'] += UNSUBSCRIBED_EMAILS_API_LIMIT
            response = self._make_request(params, BrazeAPIEndpoints.UNSUBSCRIBED_EMAILS, REQUEST_TYPE_GET)
            emails = response.get('emails', [])
            unsubscribed_emails.extend(emails)

        return unsubscribed_emails
