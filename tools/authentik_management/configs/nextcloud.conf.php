
# Arquivo: /var/www/html/config/config.php (Nextcloud)

# OpenID Connect Login via Authentik
'oidc_login_provider_url' => 'https://auth.rpa4all.com/application/o/nextcloud/',
'oidc_login_client_id' => 'authentik-nextcloud',
'oidc_login_client_secret' => 'nextcloud-sso-secret-2026',
'oidc_login_scope' => 'openid profile email',
'oidc_login_use_access_token_payload' => false,
'oidc_login_button_text' => 'Log in with Authentik',
'oidc_login_hide_password_form' => false,
'oidc_login_default_group' => 'oidc',
'oidc_login_use_access_token_payload' => false,
'oidc_create_groups' => true,
'oidc_login_webdav_enabled' => false,
'oidc_login_auto_redirect' => false,
'oidc_login_logout_url' => 'https://auth.rpa4all.com/application/o/token/revoke/',
