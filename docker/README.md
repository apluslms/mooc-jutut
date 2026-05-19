# run-mooc-jutut

Docker container for running [MOOC-Jutut](https://github.com/apluslms/mooc-jutut).
This is intended for local development and testing.

# Usage

MOOC-jutut is installed in `/srv/jutut`.
You can mount development version of the source code to `/src/jutut`.
The container will then copy it to `/srv/jutut` and compile
the translation file (django.mo). If you mount directly to
`/srv/jutut`, you need to manually compile the translation file beforehand,
but on the other hand, Django can reload the code and restart the server
without restarting the whole container when you edit the source code files.

You can mount development version of the MOOC-Jutut source code on top of that, if you wish.

Location `/data` is a volume and contains the database and secret key.
It is world writable, so you can run this container as normal user.

You may enable the [Django Debug Toolbar](https://pypi.org/project/django-debug-toolbar/)
(a set of panels in the web browser that display useful debug information)
by setting the Django setting `ENABLE_DJANGO_DEBUG_TOOLBAR` to `True`.
It is easy to do that via the environment variable `JUTUT_ENABLE_DJANGO_DEBUG_TOOLBAR`.
See the `docker-compose.yml` example below.

Using the VS Code Python debugger is easy with the container.
VS Code can attach to the container even when VS Code is running in the host machine
and the Jutut app inside a container. In the `docker-compose.yml` example below,
the `command` starts debugpy inside the container.
The VS Code debugging settings are given in the `launch.json` example further below.

Partial example of `docker-compose.yml` (volumes are optional of course):

```yaml
services:
  jutut:
    image: apluslms/run-mooc-jutut:3.1
    # Start debugpy when you want to debug remotely in VS Code.
    #command: "python3 -m debugpy --wait-for-client --listen 0.0.0.0:5678 manage.py runserver 0.0.0.0:8082"
    #command: "python3 -m debugpy --listen 0.0.0.0:5678 manage.py runserver 0.0.0.0:8082"
    environment:
        JUTUT_ENABLE_DJANGO_DEBUG_TOOLBAR: 'false'
    volumes:
      # named persistent volume (until removed)
      - data:/data
      # mount development version to /src/jutut
      #- /home/user/mooc-jutut/:/src/jutut/:ro
      # or to /srv/jutut
      #- /home/user/mooc-jutut/:/srv/jutut/:ro
    ports:
      - "8082:8082"
      # port 5678 inside the container is used by debugpy (VS Code debugger)
      - "5677:5678"

  grader:
    image: apluslms/run-mooc-grader:1.31
    #command: "python3 -m debugpy --wait-for-client --listen 0.0.0.0:5678 manage.py runserver 0.0.0.0:8080"
    volumes:
      - data:/data
      - /var/run/docker.sock:/var/run/docker.sock
      - /tmp/aplus:/tmp/aplus
      # mount a course directory
      #- $HOME/courses/aplus-manual:/srv/courses/default:ro
      #- $HOME/mooc-grader/:/srv/grader/:ro
    ports:
      - "8080:8080"
      - "5679:5678"
  plus:
    image: apluslms/run-aplus-front:1.31
    #command: "python3 -m debugpy --wait-for-client --listen 0.0.0.0:5678 manage.py runserver 0.0.0.0:8000"
    environment:
      APLUS_ENABLE_DJANGO_DEBUG_TOOLBAR: 'false'
    volumes:
      - data:/data
      #- $HOME/a-plus/:/srv/aplus/:ro
    ports:
      - "8000:8000"
      - "5678:5678"
    depends_on:
      - grader

volumes:
  data:
```

VS Code debugger settings `launch.json`.
Place in `mooc-jutut/.vscode/launch.json` (in the mooc-jutut source code directory).

```
{
    // Use IntelliSense to learn about possible attributes.
    // Hover to view descriptions of existing attributes.
    // For more information, visit: https://go.microsoft.com/fwlink/?linkid=830387
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Remote Attach: Jutut Python",
            "type": "python",
            "request": "attach",
            "connect": {
                "host": "localhost",
                "port": 5677
            },
            "pathMappings": [
                {
                    "localRoot": "${workspaceFolder}",
                    "remoteRoot": "/srv/jutut"
                }
            ],
            "justMyCode": false
        }
    ]
}
```
