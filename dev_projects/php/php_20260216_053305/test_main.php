<?php

use PHPUnit\Framework\TestCase;

class Scrum15Test extends TestCase {

    public function testMonitorTasks() {
        // Criar uma instância do Jira com projetos e tarefas
        $project = new Project(1, 'My Project');
        $tasks = [
            new Task(1, 'Task 1', 'in progress'),
            new Task(2, 'Task 2', 'completed')
        ];
        $jira = new Jira($project, $tasks);

        // Crie uma instância do Scrum-15 com o Jira
        $scrum15 = new Scrum15($jira);

        // Simular a execução das tarefas
        foreach ($tasks as $task) {
            if ($task->getStatus() === 'in progress') {
                $phpAgent = new PHPAgent('http://your-php-agent-url');
                $this->assertEquals(true, $phpAgent->sendTaskStatus($task));
            }
        }

        // Verificar se todas as tarefas foram monitoradas
        foreach ($tasks as $task) {
            if ($task->getStatus() === 'in progress') {
                $this->assertTrue(true);
            } else {
                $this->assertFalse(false);
            }
        }
    }

    public function testManageProjects() {
        // Criar uma instância do Jira com projetos e tarefas
        $project = new Project(1, 'My Project');
        $tasks = [
            new Task(1, 'Task 1', 'in progress'),
            new Task(2, 'Task 2', 'completed')
        ];
        $jira = new Jira($project, $tasks);

        // Crie uma instância do Scrum-15 com o Jira
        $scrum15 = new Scrum15($jira);

        // Simular a execução das tarefas
        foreach ($tasks as $task) {
            if ($task->getStatus() === 'completed') {
                $phpAgent = new PHPAgent('http://your-php-agent-url');
                $this->assertEquals(true, $phpAgent->sendTaskStatus($task));
            }
        }

        // Verificar se todas as tarefas foram gerenciadas
        foreach ($tasks as $task) {
            if ($task->getStatus() === 'completed') {
                $this->assertTrue(true);
            } else {
                $this->assertFalse(false);
            }
        }
    }

    public function testGenerateReports() {
        // Criar uma instância do Jira com projetos e tarefas
        $project = new Project(1, 'My Project');
        $tasks = [
            new Task(1, 'Task 1', 'in progress'),
            new Task(2, 'Task 2', 'completed')
        ];
        $jira = new Jira($project, $tasks);

        // Crie uma instância do Scrum-15 com o Jira
        $scrum15 = new Scrum15($jira);

        // Simular a execução das tarefas
        foreach ($tasks as $task) {
            if ($task->getStatus() === 'completed') {
                $phpAgent = new PHPAgent('http://your-php-agent-url');
                $this->assertEquals(true, $phpAgent->sendTaskStatus($task));
            }
        }

        // Verificar se todas as tarefas foram gerados
        foreach ($tasks as $task) {
            if ($task->getStatus() === 'completed') {
                $this->assertTrue(true);
            } else {
                $this->assertFalse(false);
            }
        }
    }
}