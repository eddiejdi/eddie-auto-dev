<?php

use PHPUnit\Framework\TestCase;
use App\JiraClient;
use App\EventLogger;

class Scrum15Test extends TestCase {
    private $jiraUrl = 'https://your-jira-url.com';
    private $username = 'your-username';
    private $password = 'your-password';

    public function setUp() {
        // Configurar o ambiente de teste
        require 'vendor/autoload.php';
        $this->scrum15 = new Scrum15($this->jiraUrl, $this->username, $this->password);
    }

    public function testStartScrum() {
        // Caso de sucesso com valores válidos
        $this->scrum15->startScrum();
        $this->assertEquals("Iniciando Scrum\n", file_get_contents('php://stdout'));

        // Caso de erro (divisão por zero)
        try {
            $this->scrum15->monitorActivities();
        } catch (\Exception $e) {
            $this->assertEquals("Erro ao monitorar atividades: Division by zero\n", $e->getMessage());
        }
    }

    public function testMonitorActivities() {
        // Caso de sucesso com valores válidos
        $tasks = [
            ['key' => 'T123', 'summary' => 'Task 1'],
            ['key' => 'T456', 'summary' => 'Task 2']
        ];
        $this->scrum15->jiraClient->setTasks($tasks);

        // Simular processamento da tarefa
        sleep(2);

        // Atualizar status da tarefa no Jira
        foreach ($tasks as $task) {
            $this->assertEquals("Tarefa Pendente: {$task['summary']}\n", file_get_contents('php://stdout'));
            $this->scrum15->jiraClient->updateTaskStatus($task['key'], 'In Progress');
        }

        // Caso de erro (divisão por zero)
        try {
            $this->scrum15->monitorActivities();
        } catch (\Exception $e) {
            $this->assertEquals("Erro ao monitorar atividades: Division by zero\n", $e->getMessage());
        }
    }

    public function testLogEvents() {
        // Caso de sucesso com valores válidos
        $events = [
            'Scrum Iniciado',
            'Monitoramento de Atividades',
            'Registro Detalhado de Eventos'
        ];
        foreach ($events as $event) {
            $this->scrum15->eventLogger->logEvent($event);
            $this->assertEquals("Log: {$event}\n", file_get_contents('php://stdout'));
        }

        // Caso de erro (divisão por zero)
        try {
            $this->scrum15->logEvents();
        } catch (\Exception $e) {
            $this->assertEquals("Erro ao registrar eventos: Division by zero\n", $e->getMessage());
        }
    }
}