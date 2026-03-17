<?php
/**
 * Roundcube - Configuração customizada para docker-mailserver self-signed certs.
 * Permite STARTTLS com certificados auto-assinados em conexões internas Docker.
 *
 * Montado em /var/roundcube/config/custom.inc.php
 * Incluído automaticamente pelo entrypoint do container Roundcube.
 */

$config['imap_conn_options'] = [
    'ssl' => [
        'verify_peer'       => false,
        'verify_peer_name'  => false,
        'allow_self_signed' => true,
    ],
];

$config['smtp_conn_options'] = [
    'ssl' => [
        'verify_peer'       => false,
        'verify_peer_name'  => false,
        'allow_self_signed' => true,
    ],
];
