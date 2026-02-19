<?php

use PHPUnit\Framework\TestCase;

class TaskTest extends TestCase {
    public function testCreateTask() {
        $task = new Task(1, 'Implementar o código PHP moderno');
        $this->assertEquals(1, $task->getId());
        $this->assertEquals('Implementar o código PHP moderno', $task->getTitle());
        $this->assertEquals('pending', $task->getStatus());
    }

    public function testSetStatus() {
        $task = new Task(1, 'Implementar o código PHP moderno');
        $task->setStatus('completed');
        $this->assertEquals('completed', $task->getStatus());
    }
}

class ReportTest extends TestCase {
    public function testAddTask() {
        $report = new Report();
        $task = new Task(2, 'Refatorar a lógica do sistema');
        $report->addTask($task);
        $this->assertEquals(1, count($report->getTasks()));
    }

    public function testGetTasks() {
        $report = new Report();
        $task1 = new Task(3, 'Atualizar o banco de dados');
        $task2 = new Task(4, 'Testar a API REST');
        $report->addTask($task1);
        $report->addTask($task2);
        $this->assertEquals([3, 4], array_keys($report->getTasks()));
    }
}

class JiraIntegrationTest extends TestCase {
    public function testCreateIssue() {
        // Implementação para criar um novo issue no Jira
        // ...
    }
}

class ActivityMonitorTest extends TestCase {
    public function testAddTask() {
        $activityMonitor = new ActivityMonitor();
        $task = new Task(5, 'Documentar o projeto');
        $activityMonitor->addTask($task);
        $this->assertEquals(1, count($activityMonitor->getTasks()));
    }

    public function testGetTasks() {
        $activityMonitor = new ActivityMonitor();
        $task1 = new Task(6, 'Organizar a equipe');
        $task2 = new Task(7, 'Estudar o novo framework');
        $activityMonitor->addTask($task1);
        $activityMonitor->addTask($task2);
        $this->assertEquals([6, 7], array_keys($activityMonitor->getTasks()));
    }
}

class DetailedReportTest extends TestCase {
    public function testGenerate() {
        // Implementação para gerar um relatório detalhado com atividades
        // ...
    }
}