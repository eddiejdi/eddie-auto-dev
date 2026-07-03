
# Arquivo: /var/www/html/config/config.php (Nextcloud)

# OpenID Connect Login via Authentik
'oidc_login_provider_url' => 'https://auth.rpa4all.com/application/o/nextcloud/',
'oidc_login_client_id' => 'authentik-nextcloud',
'oidc_login_client_secret' => getenv('AUTHENTIK_NEXTCLOUD_CLIENT_SECRET') ?: '!!SET_VIA_ENV!!',
'oidc_login_scope' => 'openid profile email groups',
'oidc_login_use_access_token_payload' => false,
'oidc_login_button_text' => 'Log in with Authentik',
'oidc_login_hide_password_form' => true,
'oidc_login_default_group' => 'users',
'oidc_login_use_access_token_payload' => false,
'oidc_create_groups' => true,
'oidc_login_webdav_enabled' => false,
'oidc_login_auto_redirect' => false,
'oidc_login_logout_url' => 'https://auth.rpa4all.com/application/o/nextcloud/end-session/',
