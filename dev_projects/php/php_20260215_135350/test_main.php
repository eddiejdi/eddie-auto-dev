<?php

// Importar classes necessárias
require_once 'JiraClient.php';
require_once 'PHPAgent.php';

class Scrum15Test extends PHPUnit\Framework\TestCase {
    private $jiraUrl = 'https://your-jira-instance.com';
    private $username = 'your-username';
    private $password;

    public function setUp() {
        // Configuração do Jira
        $this->jiraClient = new JiraClient($this->jiraUrl, $this->username, $this->password);
        $this->phpAgent = new PHPAgent();
    }

    public function testRegisterEventWithValidData() {
        // Evento a ser registrado
        $event = 'User registered on the platform';

        // Registrar o evento
        $this->scrum15->registerEvent($event);

        // Verificar se o evento foi registrado no PHP Agent
        $this->assertTrue($this->phpAgent->hasRegisteredEvent($event));

        // Verificar se o evento foi adicionado ao Jira
        $issueId = $this->jiraClient->createIssue('Scrum 15 Event', 'This is a test event for Scrum 15');
        $this->assertTrue($this->jiraClient->hasCommentOnIssue($issueId, $event));
    }

    public function testRegisterEventWithInvalidData() {
        // Evento com valor inválido
        $event = '';

        // Registrar o evento
        $this->scrum15->registerEvent($event);

        // Verificar se o evento foi registrado no PHP Agent
        $this->assertFalse($this->phpAgent->hasRegisteredEvent($event));

        // Verificar se o evento não foi adicionado ao Jira
        $issueId = $this->jiraClient->createIssue('Scrum 15 Event', 'This is a test event for Scrum 15');
        $this->assertFalse($this->jiraClient->hasCommentOnIssue($issueId, $event));
    }

    // Adicionar mais testes conforme necessário
}