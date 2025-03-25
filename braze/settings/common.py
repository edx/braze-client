"""
braze common settings.
"""


def plugin_settings(settings):
    """
    Common settings for braze app
    """
    env_tokens = getattr(settings, "ENV_TOKENS", {})

    # BRAZE API SETTINGS
    settings.EDX_BRAZE_API_KEY = env_tokens.get("EDX_BRAZE_API_KEY", None)
    settings.EDX_BRAZE_API_SERVER = env_tokens.get("EDX_BRAZE_API_SERVER", None)
    settings.BRAZE_COURSE_ENROLLMENT_CANVAS_ID = env_tokens.get(
        "BRAZE_COURSE_ENROLLMENT_CANVAS_ID", ""
    )
