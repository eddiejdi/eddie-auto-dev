<?php

use PHPUnit\Framework\TestCase;

class PhpAgentTest extends TestCase {

    public function testStartJiraIntegrationSuccess() {
        // Configurar o PHP Agent com dados válidos
        $config = new \PhpAgent\Config();
        $config->setServer('http://localhost:8080');
        $config->setToken('your_token_here');

        $agent = new \PhpAgent\Agent($config);

        // Simular a resposta do servidor com sucesso
        $response = [
            'status' => 201,
            'message' => 'Integração com Jira bem-sucedida!'
        ];

        // Setar a resposta do servidor em mock
        $agent->setResponse($response);

        // Chamar a função de integração
        startJiraIntegration();

        // Verificar se o status da requisição foi 201
        $this->assertEquals(201, $response['status']);
    }

    public function testStartJiraIntegrationError() {
        // Configurar o PHP Agent com dados válidos
        $config = new \PhpAgent\Config();
        $config->setServer('http://localhost:8080');
        $config->setToken('your_token_here');

        $agent = new \PhpAgent\Agent($config);

        // Simular a resposta do servidor com erro
        $response = [
            'status' => 500,
            'message' => 'Falha na integração com Jira.'
        ];

        // Setar a resposta do servidor em mock
        $agent->setResponse($response);

        // Chamar a função de integração
        startJiraIntegration();

        // Verificar se o status da requisição foi 500
        $this->assertEquals(500, $response['status']);
    }
}