<?php

// Importar classes necessárias
require 'vendor/autoload.php';

use PhpAgent\Jira\Client;
use PhpAgent\Jira\Issue;

class JiraIntegration
{
    private $client;
    private $issue;

    public function __construct($jiraUrl, $username, $password)
    {
        $this->client = new Client($jiraUrl);
        $this->client->login($username, $password);

        // Criar uma nova issue (se necessário)
        $this->issue = new Issue();
        $this->issue->setSummary('Teste de Integração PHP Agent com Jira');
        $this->issue->setDescription('Este é um teste para verificar a integração do PHP Agent com Jira.');
    }

    public function createIssue()
    {
        try {
            $this->client->createIssue($this->issue);
            echo "Issue criado com sucesso.\n";
        } catch (\Exception $e) {
            echo "Erro ao criar issue: " . $e->getMessage() . "\n";
        }
    }

    public function updateIssue()
    {
        try {
            // Atualizar o status da issue
            $this->issue->setStatus('In Progress');
            $this->client->updateIssue($this->issue);
            echo "Issue atualizado com sucesso.\n";
        } catch (\Exception $e) {
            echo "Erro ao atualizar issue: " . $e->getMessage() . "\n";
        }
    }

    public function deleteIssue()
    {
        try {
            // Deletar a issue
            $this->client->deleteIssue($this->issue);
            echo "Issue deletado com sucesso.\n";
        } catch (\Exception $e) {
            echo "Erro ao deletar issue: " . $e->getMessage() . "\n";
        }
    }

    public static function main()
    {
        // Configuração do Jira
        $jiraUrl = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        // Instanciar a classe JiraIntegration
        $integration = new JiraIntegration($jiraUrl, $username, $password);

        // Criar uma nova issue
        $integration->createIssue();

        // Atualizar o status da issue
        $integration->updateIssue();

        // Deletar a issue
        $integration->deleteIssue();
    }
}

// Executar o script principal
JiraIntegration::main();