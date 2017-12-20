Production installation
=======================

Environment
-----------

### Install following software in to your system:

* git
* nginx
* PostgreSQL
* memcached
* RabbitMQ
* GNU gettext
* python 3
* python 3 virtualenv
* python 3 psycopg2
* python 3 certifi (used to get up-to-date CA list from system)


#### Debian:

```sh
sudo apt-get -y install \
  git nginx postgresql memcached rabbitmq-server gettext \
  python3 python-virtualenv python3-psycopg2 python3-certifi
```

### Setup environment

#### Use installtion script

**Debian note**: You should probably remove nginx default server `rm /etc/nginx/sites-enabled/*`.

Create user, clone repo and init config files.

```sh
wget 'https://raw.githubusercontent.com/Aalto-LeTech/mooc-jutut/master/scripts/install.py' -O-|sudo python3 - \
 --user=jutut --home=/opt/jutut --fqdn=jutut.example.com
```

Edit files `/opt/jutut/mooc-jutut/install_config.ini` and `/opt/jutut/mooc-jutut/jutut/local_settings.py` for your needs.


```sh
sudo /opt/jutut/mooc-jutut/scripts/install.py install
```

If everythin is ok, then finalise with

```sh
sudo /opt/jutut/mooc-jutut/scripts/install.py online
```

You can read server logs using `journalctl -t mooc-jutut` or follow with `journalctl -t mooc-jutut -f`.


#### Or do manually at least following steps

* Create user

  ```sh
  adduser --system --disabled-password \
  --gecos 'MOOC Jutut webapp server,,,' \
  --home /opt/jutut --group nogroup jutut
  ```

* Configure DB
* Configure rabbitmq
* Configure nginx
* Configure systemd services (checkout `scripts/templates/` for templates)
* Clone repo / checkout new brnach
* Install virtual env
* Link python packages from the system

  ```sh
  sudo -H -u jutut sh -c "
    for p in certifi psycopg2; do
      for d in /opt/jutut/venv/lib/python3*; do
        psrc=\$(python3 -c \"import \$p; print(\$p.__file__)\")
        rm \$d/site-packages/\$p-*.egg-info
        ln -s -t \$d/site-packages/ \${psrc%/*}*
      done
    done"
  ```

* Install requirements.txt
* Install gunicorn
* Configure local_settings.py
* Django migrate
* Django compilemessages
* Django collectstatic
