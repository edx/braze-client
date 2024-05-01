"""
Constants for the braze client.
"""


class BrazeAPIEndpoints:
    """
    Braze endpoints.
    """

    SEND_CAMPAIGN = '/campaigns/trigger/send'
    SEND_CANVAS = '/canvas/trigger/send'
    EXPORT_IDS = '/users/export/ids'
    SEND_MESSAGE = '/messages/send'
    NEW_ALIAS = '/users/alias/new'
    TRACK_USER = '/users/track'
    IDENTIFY_USERS = '/users/identify'
    UNSUBSCRIBE_USER_EMAIL = '/email/status'
    UNSUBSCRIBED_EMAILS = '/email/unsubscribes'


# Braze enforced request size limits
REQUEST_TYPE_GET = 'get'
REQUEST_TYPE_POST = 'post'
TRACK_USER_COMPONENT_CHUNK_SIZE = 75
USER_ALIAS_CHUNK_SIZE = 50

# https://www.braze.com/docs/api/endpoints/export/user_data/post_users_identifier/?tab=all%20fields
GET_EXTERNAL_IDS_CHUNK_SIZE = 50

# https://www.braze.com/docs/api/endpoints/user_data/post_user_identify/
MAX_NUM_IDENTIFY_USERS_ALIASES = 50

UNSUBSCRIBED_STATE = 'unsubscribed'
UNSUBSCRIBED_EMAILS_API_LIMIT = 500
UNSUBSCRIBED_EMAILS_API_SORT_DIRECTION = 'desc'
