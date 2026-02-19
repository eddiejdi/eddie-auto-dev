<?php

use PHPUnit\Framework\TestCase;
use Jira\Client;
use Jira\Issue;

class Scrum15Test extends TestCase {
    private $jiraClient;
    private $issueTracker;

    public function setUp() {
        // Configurar a conexão com o Jira
        $this->jiraUrl = 'https://your-jira-instance.atlassian.net';
        $this->username = 'your-username';
        $this->password = 'your-password';

        // Criar uma instância do Scrum15
        $this->scrum15 = new Scrum15($this->jiraUrl, $this->username, $this->password);
    }

    public function testRegisterEvent() {
        // Caso de sucesso com valores válidos
        $eventName = 'User Login';
        $eventData = "Usuário {$this->username} logou no sistema.";
        $this->scrum15->registerEvent($eventName, $eventData);

        // Verificar se o evento foi registrado corretamente
        $issueKey = 'SCRUM15-1';
        $issues = $this->issueTracker.searchIssues(['key' => $issueKey]);
        $this->assertCount(1, $issues);
        $issue = $issues[0];
        $this->assertEquals($eventName, $issue->getDescription());
        $this->assertEquals($eventData, $issue->getComments()[0]->getBody());

        // Caso de erro (divisão por zero)
        $eventName = 'User Login';
        $eventData = "Usuário {$this->username} logou no sistema.";
        $this->scrum15->registerEvent($eventName, $eventData);

        // Verificar se o evento foi registrado corretamente
        $issueKey = 'SCRUM15-1';
        $issues = $this->issueTracker.searchIssues(['key' => $issueKey]);
        $this->assertCount(2, $issues);
    }

    public function testMonitorActivity() {
        // Caso de sucesso com valores válidos
        $user = 'username';
        $issues = $this->scrum15->monitorActivity();

        // Verificar se as atividades foram monitoradas corretamente
        $this->assertNotEmpty($issues);
    }

    public static function main() {
        // Executar o código principal
        Scrum15::main();
    }
}