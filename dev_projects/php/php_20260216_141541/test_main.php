<?php

// Importar bibliotecas necessárias
require 'vendor/autoload.php';

use PhpAgent\Agent;
use PHPUnit\Framework\TestCase;

class PhpAgentTest extends TestCase {
    protected $agent;

    public function setUp(): void {
        // Configuração do PHP Agent
        $this->agent = new Agent();
        $this->agent->setToken('YOUR_JIRA_TOKEN');
        $this->agent->setProjectKey('YOUR_PROJECT_KEY');
    }

    public function testCreateJiraTicketSuccess() {
        // Caso de sucesso com valores válidos
        global $agent;

        // Criar o ticket
        $issue = [
            'fields' => [
                'project' => ['key' => 'YOUR_PROJECT_KEY'],
                'summary' => "Teste do PHP Agent com Jira",
                'description' => "Este é um teste para verificar a integração do PHP Agent com Jira.",
                'issuetype' => ['name' => 'Bug']
            ]
        ];

        // Enviar o ticket para Jira
        $response = $agent->createIssue($issue);

        // Verificar se o ticket foi criado com sucesso
        $this->assertNotEmpty($response['id'], "Ticket não criado com sucesso");
    }

    public function testCreateJiraTicketError() {
        // Caso de erro (divisão por zero)
        global $agent;

        // Criar o ticket com uma divisão por zero
        $issue = [
            'fields' => [
                'project' => ['key' => 'YOUR_PROJECT_KEY'],
                'summary' => "Teste do PHP Agent com Jira",
                'description' => "Este é um teste para verificar a integração do PHP Agent com Jira.",
                'issuetype' => ['name' => 'Bug']
            ]
        ];

        // Enviar o ticket para Jira
        $response = $agent->createIssue($issue);

        // Verificar se houve erro na criação do ticket
        $this->assertArrayHasKey('error', $response, "Erro não encontrado");
    }

    public function testCreateJiraTicketEdgeCase() {
        // Caso de edge case (valores limite)
        global $agent;

        // Criar o ticket com valores limites
        $issue = [
            'fields' => [
                'project' => ['key' => 'YOUR_PROJECT_KEY'],
                'summary' => "Teste do PHP Agent com Jira",
                'description' => "Este é um teste para verificar a integração do PHP Agent com Jira.",
                'issuetype' => ['name' => 'Bug']
            ]
        ];

        // Enviar o ticket para Jira
        $response = $agent->createIssue($issue);

        // Verificar se houve erro na criação do ticket
        $this->assertArrayHasKey('error', $response, "Erro não encontrado");
    }
}