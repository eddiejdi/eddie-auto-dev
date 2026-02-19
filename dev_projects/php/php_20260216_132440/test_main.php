<?php

use PHPUnit\Framework\TestCase;

class MonitorServiceTest extends TestCase {
    public function setUp() {
        // Configurar a conexão com o Jira (não necessário para este teste)
    }

    public function testMonitorProcessesWithValidProcesses() {
        $jiraClient = new MockJiraClient();
        $monitorService = new MonitorService($jiraClient);

        $processes = [
            new Process(1, 'Process A'),
            new Process(2, 'Process B'),
            new Process(3, 'Process C')
        ];

        foreach ($processes as $process) {
            $this->logEvent($monitorService, $process);
        }

        // Verifique se o número de eventos criados no Jira está correto
        $this->assertEquals(count($jiraClient->events), count($processes));
    }

    public function testMonitorProcessesWithInvalidProcess() {
        $jiraClient = new MockJiraClient();
        $monitorService = new MonitorService($jiraClient);

        // Criar um processo inválido
        $invalidProcess = new Process(null, 'Invalid Process');

        try {
            $this->logEvent($monitorService, $invalidProcess);
            $this->fail('Expected an exception to be thrown');
        } catch (\Exception $e) {
            // Verifique se o erro é do tipo esperado
            $this->assertEquals($e->getMessage(), 'Invalid process ID provided');
        }
    }

    private function logEvent(MonitorService $monitorService, Process $process) {
        $event = new Event(
            uniqid(),
            $process->getId(),
            'Process started'
        );

        try {
            $monitorService->logEvent($event);
            echo "Event logged: {$event->getId()}\n";
        } catch (\Exception $e) {
            echo "Error logging event: {$e->getMessage()}\n";
        }
    }
}

class MockJiraClient {
    public function events = [];

    public function createIssue(Event $event) {
        // Simulação de criação de issue no Jira
        $this->events[] = $event;
        echo "Creating issue in Jira...\n";
    }
}