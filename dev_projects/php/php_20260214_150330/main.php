<?php

// Importar bibliotecas necessárias
require 'vendor/autoload.php';

use Jira\Client;
use Jira\Issue;

class Scrum15 {
    private $jiraClient;
    private $issueId;

    public function __construct($jiraUrl, $username, $password, $issueId) {
        $this->jiraClient = new Client($jiraUrl);
        $this->jiraClient->login($username, $password);
        $this->issueId = $issueId;
    }

    public function monitorarProcesso() {
        // Simulação de processamento
        sleep(5);

        return "Processo concluído";
    }

    public function relatorioAtividade() {
        $issue = new Issue($this->jiraClient, $this->issueId);
        $summary = $issue->getSummary();
        $status = $issue->getStatus();

        return "Relatório de atividade para {$summary}: {$status}";
    }

    public static function main() {
        // Configuração do Jira
        $jiraUrl = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';
        $issueId = 'YOUR-ISSUE-ID';

        // Criar instância da classe Scrum15
        $scrum15 = new Scrum15($jiraUrl, $username, $password, $issueId);

        try {
            // Monitorar processo
            $processoStatus = $scrum15->monitorarProcesso();
            echo "Status do processo: {$processoStatus}\n";

            // Relatório de atividade
            $relatorioAtividade = $scrum15->relatorioAtividade();
            echo "Relatório de atividade:\n{$relatorioAtividade}\n";
        } catch (Exception $e) {
            echo "Erro: {$e->getMessage()}\n";
        }
    }
}

if (__name__ == "__main__") {
    Scrum15::main();
}