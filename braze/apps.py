"""
braze Django application initialization.
"""

from django.apps import AppConfig
from edx_django_utils.plugins.constants import PluginSettings


class BrazeAppConfig(AppConfig):
    """
    Configuration for the braze Django application.
    """

    name = 'braze'

    plugin_app = {
        PluginSettings.CONFIG: {
            'lms.djangoapp': {
                'common': {PluginSettings.RELATIVE_PATH: 'settings.common'},
                'production': {PluginSettings.RELATIVE_PATH: 'settings.production'},
                'devstack': {PluginSettings.RELATIVE_PATH: 'settings.devstack'},
            },
            'cms.djangoapp': {
                'common': {PluginSettings.RELATIVE_PATH: 'settings.common'},
                'production': {PluginSettings.RELATIVE_PATH: 'settings.production'},
                'devstack': {PluginSettings.RELATIVE_PATH: 'settings.devstack'},
            },
        },
    }
