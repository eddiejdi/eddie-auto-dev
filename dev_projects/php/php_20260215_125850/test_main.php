<?php

use PHPUnit\Framework\TestCase;

class DockerTest extends TestCase {
    public function testStartDocker() {
        $config = [
            'image' => 'jira-php-agent',
            'container_name' => 'jira-php-agent-container',
            'ports' => [
                ['host_port' => 8080, 'container_port' => 8080],
            ],
        ];

        startDocker($config);

        // Verifica se o container foi criado
        $this->assertFileExists("/var/run/docker.sock");
    }

    public function testStartPhpAgent() {
        $dockerConfig = [
            'image' => 'jira-php-agent',
            'container_name' => 'jira-php-agent-container',
            'ports' => [
                ['host_port' => 8080, 'container_port' => 8080],
            ],
        ];

        startDocker($dockerConfig);

        // Inicia o PHP Agent no Docker
        $command = "docker exec -it {$dockerConfig['container_name']} php artisan schedule:run";
        exec($command);

        // Verifica se o PHP Agent foi iniciado corretamente
        $this->assertFileExists("/var/run/php-agent.pid");
    }
}