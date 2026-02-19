<?php

// Configuração do Docker
$dockerConfig = [
    'image' => 'jira-php-agent',
    'container_name' => 'jira-php-agent-container',
    'ports' => [
        ['host_port' => 8080, 'container_port' => 8080],
    ],
];

// Função para iniciar o Docker
function startDocker($config) {
    $command = "docker run -d --name {$config['container_name']} -p " . implode(',', array_map(function ($port) { return "{$port[0]}:{$port[1]}"; }, $config['ports'])) . " {$config['image']}";
    exec($command);
}

// Função para iniciar o PHP Agent no Docker
function startPhpAgent() {
    // Implemente a lógica para iniciar o PHP Agent no Docker
    // Por exemplo, usando o comando docker exec
    $command = "docker exec -it {$dockerConfig['container_name']} php artisan schedule:run";
    exec($command);
}

// Função principal do programa
function main() {
    startDocker($dockerConfig);
    startPhpAgent();
}

// Verifica se o script é executado diretamente e não importado
if (__name__ == "__main__") {
    main();
}