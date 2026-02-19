<?php

use PHPUnit\Framework\TestCase;

class Scrum15Test extends TestCase {

    public function setUp() {
        $this->jiraClient = new JiraClient('https://your-jira-url.com', 'username', 'password');
        $this->logAnalyzer = new LogAnalyzer();
        $this->taskManager = new TaskManager();
        $this->reportGenerator = new ReportGenerator();
    }

    public function testRun() {
        // Caso de sucesso com valores válidos
        $logs = ['log1', 'log2'];
        $tasks = $this->taskManager->manageTasks($logs);
        $reports = $this->reportGenerator->generateReports($tasks);

        $this->assertNotEmpty($reports, "O relatório deve ser gerado");
    }

    public function testRunWithInvalidLogs() {
        // Caso de erro (divisão por zero)
        $logs = ['log1', 'log2'];
        $this->taskManager->manageTasks($logs);

        try {
            $reports = $this->reportGenerator->generateReports($tasks);
            $this->fail("O relatório deve gerar uma exceção");
        } catch (Exception $e) {
            $this->assertEquals('Divide by zero', $e->getMessage(), "A exceção deve ser 'Divide by zero'");
        }
    }

    public function testRunWithInvalidTaskManager() {
        // Caso de erro (valores inválidos)
        $logs = ['log1', 'log2'];
        $this->taskManager = new TaskManager();
        $reports = $this->reportGenerator->generateReports($tasks);

        try {
            $reports = $this->reportGenerator->generateReports($tasks);
            $this->fail("O relatório deve gerar uma exceção");
        } catch (Exception $e) {
            $this->assertEquals('Invalid task manager', $e->getMessage(), "A exceção deve ser 'Invalid task manager'");
        }
    }

    public function testRunWithNullLogs() {
        // Caso de edge case (valores limite)
        $logs = null;
        $tasks = $this->taskManager->manageTasks($logs);
        $reports = $this->reportGenerator->generateReports($tasks);

        $this->assertEmpty($reports, "O relatório deve ser gerado");
    }
}