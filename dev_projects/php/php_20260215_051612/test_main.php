<?php

// Importar as bibliotecas necessárias
require 'vendor/autoload.php';

class PhpAgentTest extends PHPUnit\Framework\TestCase {

    public function testSendLogToJiraSuccess() {
        // Configurações do Jira API
        $url = 'http://your-jira-url/rest/api/2/log';
        $headers = [
            'Content-Type: application/json',
            'Authorization: Basic your-api-key'
        ];

        // JSON da log
        $jsonLog = json_encode([
            'log' => 'Teste de log',
            'level' => 'info'
        ]);

        // Faz a requisição POST para Jira
        $ch = curl_init($url);
        curl_setopt($ch, CURLOPT_POST, 1);
        curl_setopt($ch, CURLOPT_POSTFIELDS, $jsonLog);
        curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);

        // Executa a requisição
        $response = curl_exec($ch);
        curl_close($ch);

        // Verifica se a resposta é válida
        $this->assertNotEmpty($response);
    }

    public function testSendLogToJiraError() {
        // Configurações do Jira API
        $url = 'http://your-jira-url/rest/api/2/log';
        $headers = [
            'Content-Type: application/json',
            'Authorization: Basic your-api-key'
        ];

        // JSON da log com erro
        $jsonLog = json_encode([
            'log' => 'Erro de log',
            'level' => 'error'
        ]);

        // Faz a requisição POST para Jira
        $ch = curl_init($url);
        curl_setopt($ch, CURLOPT_POST, 1);
        curl_setopt($ch, CURLOPT_POSTFIELDS, $jsonLog);
        curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);

        // Executa a requisição
        $response = curl_exec($ch);
        curl_close($ch);

        // Verifica se a resposta é válida e contém um erro
        $this->assertNotEmpty($response);
        $this->assertStringContainsString('Erro', $response);
    }

    public function testCapturePhpAgentDataSuccess() {
        // Simula o envio de dados do PHP Agent
        file_put_contents('php://input', json_encode([
            'log' => 'Teste de log',
            'level' => 'info'
        ]));

        // Chama a função principal do sistema
        main();

        // Verifica se o log foi enviado para Jira
        $this->assertFileExists('logs.txt');
        $this->assertNotEmpty(file_get_contents('logs.txt'));
    }

    public function testCapturePhpAgentDataError() {
        // Simula um envio de dados do PHP Agent com erro
        file_put_contents('php://input', json_encode([
            'log' => 'Erro de log',
            'level' => 'error'
        ]));

        // Chama a função principal do sistema
        main();

        // Verifica se o log foi enviado para Jira
        $this->assertFileExists('logs.txt');
        $this->assertNotEmpty(file_get_contents('logs.txt'));
    }
}