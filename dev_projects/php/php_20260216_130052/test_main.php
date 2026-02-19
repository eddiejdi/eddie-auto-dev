<?php

use PhpAgent\JiraClient;
use PhpAgent\EventLogger;

class JiraScrum15Test extends PHPUnit\Framework\TestCase {

    public function setUp() {
        // Configurar as credenciais do Jira
        $this->jiraUrl = 'https://your-jira-instance.atlassian.net';
        $username = 'your-username';
        $password = 'your-password';

        // Criar uma instância da classe JiraScrum15
        $this->scrum15 = new JiraScrum15($this->jiraUrl, $username, $password);
    }

    public function testMonitorarAtividades() {
        // Mock do cliente do Jira
        $mockJiraClient = $this->createMock(JiraClient::class);
        $mockJiraClient->method('getTasks')->willReturn([
            new \PhpAgent\Task(['key' => 'T1', 'status' => 'in_progress']),
            new \PhpAgent\Task(['key' => 'T2', 'status' => 'completed'])
        ]);

        // Mock do logger de eventos
        $mockEventLogger = $this->createMock(EventLogger::class);
        $mockEventLogger->method('logEvent')->willReturn(null);

        // Configurar o mock do cliente do Jira e do logger de eventos
        $this->scrum15->jiraClient = $mockJiraClient;
        $this->scrum15->eventLogger = $mockEventLogger;

        // Executar a função monitorarAtividades
        $this->scrum15->monitorarAtividades();

        // Verificar se o logger de eventos foi chamado corretamente
        $this->assertEquals(2, $mockEventLogger->methodCallCount('logEvent'));
    }

    public function testRegistrarEventos() {
        // Mock do cliente do Jira
        $mockJiraClient = $this->createMock(JiraClient::class);
        $mockJiraClient->method('getTasks')->willReturn([
            new \PhpAgent\Task(['key' => 'T1', 'status' => 'in_progress']),
            new \PhpAgent\Task(['key' => 'T2', 'status' => 'completed'])
        ]);

        // Mock do logger de eventos
        $mockEventLogger = $this->createMock(EventLogger::class);
        $mockEventLogger->method('logEvent')->willReturn(null);

        // Configurar o mock do cliente do Jira e do logger de eventos
        $this->scrum15->jiraClient = $mockJiraClient;
        $this->scrum15->eventLogger = $mockEventLogger;

        // Executar a função registrarEventos
        $this->scrum15->registrarEventos();

        // Verificar se o logger de eventos foi chamado corretamente
        $this->assertEquals(2, $mockEventLogger->methodCallCount('logEvent'));
    }

    public function testMonitorarAtividadesErro() {
        // Mock do cliente do Jira
        $mockJiraClient = $this->createMock(JiraClient::class);
        $mockJiraClient->method('getTasks')->willThrowException(new \Exception('Erro ao listar tarefas'));

        // Mock do logger de eventos
        $mockEventLogger = $this->createMock(EventLogger::class);
        $mockEventLogger->method('logEvent')->willReturn(null);

        // Configurar o mock do cliente do Jira e do logger de eventos
        $this->scrum15->jiraClient = $mockJiraClient;
        $this->scrum15->eventLogger = $mockEventLogger;

        // Executar a função monitorarAtividades
        try {
            $this->scrum15->monitorarAtividades();
        } catch (\Exception $e) {
            // Verificar se o erro foi capturado corretamente
            $this->assertEquals('Erro ao listar tarefas', $e->getMessage());
        }
    }

    public function testRegistrarEventosErro() {
        // Mock do cliente do Jira
        $mockJiraClient = $this->createMock(JiraClient::class);
        $mockJiraClient->method('getTasks')->willThrowException(new \Exception('Erro ao listar tarefas'));

        // Mock do logger de eventos
        $mockEventLogger = $this->createMock(EventLogger::class);
        $mockEventLogger->method('logEvent')->willReturn(null);

        // Configurar o mock do cliente do Jira e do logger de eventos
        $this->scrum15->jiraClient = $mockJiraClient;
        $this->scrum15->eventLogger = $mockEventLogger;

        // Executar a função registrarEventos
        try {
            $this->scrum15->registrarEventos();
        } catch (\Exception $e) {
            // Verificar se o erro foi capturado corretamente
            $this->assertEquals('Erro ao listar tarefas', $e->getMessage());
        }
    }
}