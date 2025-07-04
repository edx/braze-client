"""
Channel for sending push notifications using braze.
"""
import logging

from django.conf import settings
from edx_ace.channel import Channel, ChannelType

from braze.client import BrazeClient

LOG = logging.getLogger(__name__)


class BrazePushNotificationChannel(Channel):
    """
    A channel for sending push notifications using braze.
    """
    channel_type = ChannelType.PUSH
    _CAMPAIGNS_SETTING = 'ACE_CHANNEL_BRAZE_PUSH_CAMPAIGNS'

    @classmethod
    def enabled(cls):
        """
        Returns: True iff braze client is available.
        """
        braze_api_key = getattr(settings, 'ACE_CHANNEL_BRAZE_PUSH_API_KEY', None)
        braze_api_url = getattr(settings, 'ACE_CHANNEL_BRAZE_REST_ENDPOINT', None)
        return bool(braze_api_key and braze_api_url)

    def deliver(self, message, rendered_message) -> None:
        """
        Transmit a rendered message to a recipient.

        Args:
            message: The message to transmit.
            rendered_message: The rendered content of the message that has been personalized
                for this particular recipient.
        """
        notification_type = message.options['notification_type']
        emails = message.options.get('emails') or [message.recipient.email_address]
        campaign_id = self._campaign_id(notification_type)
        if not campaign_id:
            LOG.info('Could not find braze campaign for notification %s', notification_type)
            return

        try:
            braze_client = self.get_braze_client()
            braze_client.send_campaign_message(
                campaign_id=campaign_id,
                trigger_properties=message.context['post_data'],
                emails=emails
            )
            LOG.info('Sent push notification for %s with Braze', notification_type)
        except Exception as exc:  # pylint: disable=broad-except
            LOG.error(
                'Unable to send push notification for %s with Braze. Reason: %s',
                notification_type,
                str(exc)
            )

    @classmethod
    def _campaign_id(cls, notification_type):
        """Returns the campaign ID for a given ACE message name or None if no match is found"""
        return getattr(settings, cls._CAMPAIGNS_SETTING, {}).get(notification_type)

    @classmethod
    def get_braze_client(cls):
        """Returns the braze client object"""
        braze_api_key = getattr(settings, 'ACE_CHANNEL_BRAZE_PUSH_API_KEY', None)
        braze_api_url = getattr(settings, 'ACE_CHANNEL_BRAZE_REST_ENDPOINT', None)

        if not braze_api_key or not braze_api_url:
            return None

        return BrazeClient(
            api_key=braze_api_key,
            api_url=f"https://{braze_api_url}",
            app_id=''
        )
