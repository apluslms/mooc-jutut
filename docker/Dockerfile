FROM apluslms/service-base:django-1.19

# Set container related configuration via environment variables
ENV CONTAINER_TYPE="jutut" \
    JUTUT_LOCAL_SETTINGS="/srv/jutut-cont-settings.py" \
    JUTUT_SECRET_KEY_FILE="/local/jutut/secret_key.py"

RUN adduser --system --no-create-home --disabled-password --gecos "MOOC Jutut webapp server,,," --home /srv/jutut --ingroup nogroup jutut \
  && mkdir /srv/jutut && chown jutut.nogroup /srv/jutut \
  && git config --global --add safe.directory /srv/jutut \
  && :

COPY docker/rootfs /
COPY . /srv/jutut

RUN cd /srv/jutut \
  # 1) prebuild .pyc files
  && python3 -m compileall -q . \
\
  # 2) install requirements, remove the file, remove unrequired locales and tests
  && pip_install -r requirements.txt \
  && pip_install -r requirements_testing.txt \
  && pip_install "django-debug-toolbar >= 6.1.0, < 7" \
  && rm requirements.txt requirements_testing.txt \
  && find /usr/local/lib/python* -type d -regex '.*/locale/[a-z_A-Z]+' -not -regex '.*/\(en\|fi\|sv\)' -print0 | xargs -0 rm -rf \
  && find /usr/local/lib/python* -type d -name 'tests' -print0 | xargs -0 rm -rf \
\
 # 3) preprocess
 && export \
    JUTUT_SECRET_KEY="-" \
    JUTUT_CACHES="{\"default\": {\"BACKEND\": \"django.core.cache.backends.dummy.DummyCache\"}}" \
 && python3 manage.py compilemessages 2>&1 \
 && create-db.sh jutut jutut django-migrate.sh \
 && :

EXPOSE 8082
WORKDIR /srv/jutut/
CMD [ "manage", "runserver", "0.0.0.0:8082" ]
