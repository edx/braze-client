Change Log
----------

..
   All enhancements and patches to braze-client will be documented
   in this file.  It adheres to the structure of https://keepachangelog.com/ ,
   but in reStructuredText instead of Markdown (for ease of incorporation into
   Sphinx documentation and the PyPI description).

   This project adheres to Semantic Versioning (https://semver.org/).

.. There should always be an "Unreleased" section for changes pending release.

Unreleased
~~~~~~~~~~

[1.0.0]
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
[Breaking Change] converts braze library to python djangoapp
This change converts braze library to python djangoapp
- modified `setup.py` file
- added `apps.py` file to configure django settings and test settings
- added `manage.py` file
- modified `pylintrc` file
- modified `tox.ini` file that uses python 3.11, 3.12 django 4.2 now as env
- modified `makefile`
- upgraded requirements with python 3.11
  - added `django`, `edx-django-utils` and `requests` packages in `base.in` file.
  - removed `tox-battery` package from `dev.in` file as it was only required by python library and now braze-client is converted from python library to python djangoapp(plugin)
- update github workflows
  - update CI workflow to use remove python 3.8 and use python 3.11, 3.12 and django4.2
  - update publish workflow to use python 3.11 instead 3.8
- bump version

[0.2.5]
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
chore: Updates version

[0.2.4]
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
feat: adds 'create_recipients' function to the braze client

[0.2.3]
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
feat: pass error response content into raised exceptions

[0.2.2]
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
fix: be defensive about pulling both ``email`` and ``external_id`` from braze export.

[0.2.1]
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
fix: be defensive about pulling external_id from braze export.

[0.2.0]
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
feat: check for external ids in batchs when creating aliases.

[0.1.8]
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
fix: always create an alias for existing profiles

[0.1.7]
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
feat: add retrieve_unsubscribed_emails method

[0.1.6]
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
feat: add unsubscribe_user_email method

[0.1.5]
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
feat: add send_canvas_message method

[0.1.4]
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
feat: add identify_users method

[0.1.3]
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
fix: handle intermittent JSONDecodeError from from Braze

[0.1.2]
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
feat: add override_frequency_capping arg for send_email

[0.1.1]
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
feat: advertise constraints in setup.py

[0.1.0] - 2021-10-20
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Added
_____

* First release on PyPI.
