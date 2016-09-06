Production installation
=======================

Environment
-----------

Install software:

* nginx
* postgresql
* git
* python 3
* python 3 virtualenv
* python 3 psycopg2
* python 3 certifi (used to get up-to-date CA list from system)

Debian:

`sudo apt-get install nginx postgresql git python3 python-virtualenv python3-psycopg2 python3-certifi`

Setup environment

```sh
user="jutut"
home="/opt/$user"
src="$home/mooc-jutut"
venv="$home/venv"
pip="$venv/bin/pip"
python="$venv/bin/python"

# create user
adduser --system --home $home --group nogroup --gecos 'MOOC Jutut webapp server,,,' --disabled-password $user`

# clone git
sudo -H -u $user git clone https://github.com/Aalto-LeTech/mooc-jutut.git $src

# install virtual env
sudo -H -u $user virtualenv --python=python3 $venv

# link system psycopg2 and certifi (you need to rerun this for pip to work if system package version updates)
sudo -H -u $user sh -c "
  for p in certifi psycopg2; do
    for d in $home/venv/lib/python3*; do
      rm \$d/site-packages/\$p-*.egg-info
      psrc=\$(python3 -c \"import \$p; print(\$p.__file__)\")
      ln -s -t \$d/site-packages/ \${psrc%/*}*
    done
  done"

# install rest of requirements
sudo -H -u $user $pip install -r $src/requirements.txt
sudo -H -u $user $pip install gunicorn

# configure database
sudo -H -u postgres createuser jutut
sudo -H -u postgres createdb -O jutut mooc_jutut_prod

# create tables
sudo -H -u $user sh -c "cd $src && $python manage.py migrate"

# compile localization
sudo -H -u $user sh -c "cd $src && $python manage.py compilemessages"

# collect static
sudo -H -u $user sh -c "cd $src && $python manage.py collectstatic --noinput"
```

Configure nginx (we presume nginx.conf includes conf.d/*)

```sh
fqdn="jutut.cs.hut.fi"

# create self signed cert and key (replace with CA signed when available)
keyfile=/etc/nginx/$fqdn.key
crtfile=/etc/nginx/$fqdn.crt
dhfile=/etc/nginx/dhparams.pem
# will prompt for certificate data
[ -f $keyfile -o -f $crtfile ] || openssl req -nodes -x509 -newkey rsa:4096 -keyout /etc/nginx/$fqdn.key -out $fqdn.crt -days 465 </dev/null
[ -f $dhfile ] || openssl dhparam -out $dhfile 2048

# create server config
cat > /etc/nginx/conf.d/$fqdn.conf <<EOF
server {
  listen 80 default_server;
  listen [::]:80 default_server ipv6only=on;
  server_name $fqdn;
  underscores_in_headers on;

  location / {
    return 302 https://\$server_name\$request_uri;
  }
}

upstream jutut {
  server unix:/run/www-jutut/gunicorn.sock;
}

server {
  listen 443 ssl;
  listen [::]:443 ssl ipv6only=on;
  server_name $fqdn;
  underscores_in_headers on;

  # certs sent to the client in SERVER HELLO are concatenated in ssl_certificate
  ssl_certificate $fqdn.crt;
  ssl_certificate_key $fqdn.key;
  ssl_dhparam dhparams.pem;

  # ssl ciphers (use: https://mozilla.github.io/server-side-tls/ssl-config-generator/)
  ssl_protocols TLSv1 TLSv1.1 TLSv1.2;
  ssl_prefer_server_ciphers on;
  ssl_ciphers HIGH:MEDIUM:!aNULL:!RC4:!ADH:!MD5;

  # cache ssl session
  ssl_session_timeout 1d;
  ssl_session_cache shared:SSL:50m;
  ssl_session_tickets off;

  # HSTS (ngx_http_headers_module is required) (15768000 seconds = 6 months)
  add_header Strict-Transport-Security max-age=15768000;

  location /static {
    alias $src/static;
  }
  location /media {
    alias $src/media;
  }
  location / {
    proxy_pass_header Server;
    proxy_set_header Host \$http_host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_redirect off;
    proxy_connect_timeout 10;
    proxy_read_timeout 30;
    proxy_pass http://jutut;
  }
}
EOF

# restart nginx
systemctl restart nginx
```

Configure systemd (same can be done using supervisord)

```sh
# create tmo files for gunicorn
cat > /etc/tmpfiles.d/www-jutut.conf <<EOF
d /run/www-jutut 0755 $user nogroup -
EOF

systemd-tmpfiles --create

# create systemd configs for gunicorn
cat > /etc/systemd/system/www-jutut-gunicorn.service <<EOF
[Unit]
Description=MOOC Jutut Gunicorn
PartOf=nginx.service

[Service]
WorkingDirectory=$src/
User=$user
Group=nogroup
PIDFile=/run/www-jutut/gunicorn.pid
Environment="PATH=$venv/bin/x"
ExecStart=$venv/bin/gunicorn --workers=3 --pid /run/www-jutut/gunicorn.pid --bind unix:/run/www-jutut/gunicorn.sock jutut.wsgi:application
ExecReload=/bin/kill -s HUP $MAINPID
ExecStop=/bin/kill -s TERM $MAINPID
RestartSec=15
Restart=always

[Install]
WantedBy=multi-user.target
EOF

¤ start the service
systemctl enable www-jutut-gunicorn.service
systemctl start www-jutut-gunicorn.service
```

Check status using:

```sh
systemctl status nginx www-jutut-*
```
