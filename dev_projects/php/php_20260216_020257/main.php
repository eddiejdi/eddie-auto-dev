<?php

// Importar classes necessárias
require_once 'JiraClient.php';
require_once 'PHPAgent.php';

class Scrum15 {
    private $jiraClient;
    private $phpAgent;

    public function __construct($jiraUrl, $jiraToken) {
        $this->jiraClient = new JiraClient($jiraUrl, $jiraToken);
        $this->phpAgent = new PHPAgent();
    }

    public function monitorarAtividades() {
        // Monitorar atividades do PHP Agent
        $atualizacao = $this->phpAgent->getAtualizacao();

        if ($atualizacao) {
            // Enviar atualização para Jira
            $this->jiraClient->enviarAtualizacao($atualizacao);
        }
    }

    public function emitirRelatorio() {
        // Emitir relatório de atividades
        $relatorio = $this->phpAgent->getRelatorio();

        if ($relatorio) {
            // Enviar relatório para Jira
            $this->jiraClient->enviarRelatorio($relatorio);
        }
    }

    public static function main() {
        $scrum15 = new Scrum15('https://your-jira-url.com', 'your-jira-token');

        try {
            $scrum15->monitorarAtividades();
            $scrum15->emitirRelatorio();
        } catch (Exception $e) {
            echo "Erro: " . $e->getMessage() . "\n";
        }
    }
}

// Executar o script
Scrum15::main();