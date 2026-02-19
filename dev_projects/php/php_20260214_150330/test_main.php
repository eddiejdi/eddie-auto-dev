<?php

use Jira\Client;
use Jira\Issue;

class Scrum15Test extends \PHPUnit\Framework\TestCase {
    private $jiraClient;
    private $issueId;

    public function setUp() {
        // Configuração do Jira
        $this->jiraUrl = 'https://your-jira-instance.atlassian.net';
        $this->username = 'your-username';
        $this->password = 'your-password';
        $this->issueId = 'YOUR-ISSUE-ID';

        // Criar instância da classe Scrum15
        $this->scrum15 = new Scrum15($this->jiraUrl, $this->username, $this->password, $this->issueId);
    }

    public function testMonitorarProcesso() {
        // Caso de sucesso com valores válidos
        $this->assertEquals("Processo concluído", $this->scrum15->monitorarProcesso());

        // Caso de erro (divisão por zero)
        try {
            $this->scrum15->monitorarProcesso();
        } catch (\Exception $e) {
            $this->assertEquals("Erro: Divisão por zero", $e->getMessage());
        }
    }

    public function testRelatorioAtividade() {
        // Caso de sucesso com valores válidos
        $issue = new Issue($this->jiraClient, $this->issueId);
        $summary = $issue->getSummary();
        $status = $issue->getStatus();

        $this->assertEquals("Relatório de atividade para {$summary}: {$status}", $this->scrum15->relatorioAtividade());

        // Caso de erro (valores inválidos)
        try {
            $this->scrum15->relatorioAtividade();
        } catch (\Exception $e) {
            $this->assertEquals("Erro: Valores inválidos", $e->getMessage());
        }
    }

    public static function main() {
        // Executar testes
        PHPUnit\Framework\TestCase::main();
    }
}