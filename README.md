
MOOC jutut
==========

A-Plus grading service that provides course module feedback gathering, response management and analysis.
Service expects that A-Plus is configured with correct form layout and layout is requested from A-Plus.
[MOOC Grader](https://github.com/Aalto-LeTech/mooc-grader) is used to configure A-Plus for this task.


Requirements
------------

* Python 3.4+
* Django 1.9+
* Postgresql 9.5+

More details of packages in installation documentation.


Installation
------------

Read [INSTALLATION.md](INSTALLATION.md) for production installation.

For development,
follow production installation guide,
but you can install server with your user in development folder and skip nginx and systemd parts.

Test it
-------

Activate virtualenv.
Run `./manage.py runserver`.
Go to `http://localhost:8000/feedback/test1/`.
