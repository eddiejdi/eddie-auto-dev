<?php

use PHPUnit\Framework\TestCase;

class PhpAgentTest extends TestCase {

    public function testConfigurarPhpAgent() {
        $jira_url = 'https://your-jira-url.com';
        $username = 'username';
        $password = 'password';

        configurar_php_agent($jira_url, $username, $password);

        // Adicione verificações para garantir que a função foi chamada corretamente
    }

    public function testRegistrarAtividade() {
        $jira_url = 'https://your-jira-url.com';
        $issue_key = 'ABC-123';
        $activity_description = 'Criado novo projeto';

        registrar_atividade($jira_url, $issue_key, $activity_description);

        // Adicione verificações para garantir que a função foi chamada corretamente
    }
}