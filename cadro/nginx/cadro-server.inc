# Shared body of the CADRO server blocks (plain HTTP in cadro.conf, TLS in cadro-tls.conf).
# Included inside `server { ... }`; the zones and the resolver are defined in cadro.conf.

root /home/frappe/cadro-data/frappe-bench/sites;

client_max_body_size 50m;
proxy_buffer_size 128k;
proxy_buffers 4 256k;
proxy_busy_buffers_size 256k;

add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "same-origin" always;
server_tokens off;

gzip on;
gzip_types text/plain text/css application/json application/javascript text/xml application/xml image/svg+xml;
gzip_min_length 1024;

location /assets {
    try_files $uri =404;
    add_header Cache-Control "max-age=31536000";
}

# Private files are authorised by the application, then served by nginx (X-Accel-Redirect).
location ~ ^/protected/(.*) {
    internal;
    try_files /$host/$1 =404;
}

location = /api/method/login {
    limit_req zone=cadro_login burst=10 nodelay;
    try_files /cadro-no-such-file @webserver;
}

# Payment webhooks for the control plane (only this path is exposed; /metrics and /v1 stay
# internal). Without the control-plane profile this answers 502.
location /cadro/webhooks/ {
    limit_req zone=cadro_webhook burst=20 nodelay;
    client_max_body_size 64k;
    set $cadro_control_plane "control-plane:8090";
    rewrite ^/cadro/webhooks/(.*)$ /webhooks/$1 break;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_read_timeout 30s;
    proxy_pass http://$cadro_control_plane;
}

location /socket.io {
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header X-Frappe-Site-Name $host;
    proxy_set_header Origin $scheme://$http_host;
    proxy_set_header Host $host;
    proxy_read_timeout 3600s;
    set $cadro_socketio "socketio:9000";
    proxy_pass http://$cadro_socketio;
}

location / {
    rewrite ^(.+)/$ $1 permanent;
    rewrite ^(.+)\.html$ $1 permanent;

    location ~ ^/files/.*\.(htm|html|svg|xml) {
        add_header Content-disposition "attachment";
        try_files /$host/public/$uri @webserver;
    }

    try_files /$host/public/$uri @webserver;
}

location @webserver {
    proxy_http_version 1.1;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Frappe-Site-Name $host;
    proxy_set_header Host $http_host;
    proxy_set_header X-Use-X-Accel-Redirect True;
    proxy_read_timeout 120s;
    proxy_redirect off;
    set $cadro_backend "bench:8000";
    proxy_pass http://$cadro_backend;
}
