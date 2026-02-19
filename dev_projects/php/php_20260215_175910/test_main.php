<?php

use PHPUnit\Framework\TestCase;

class TaskManagerTest extends TestCase {
    private $taskManager;

    protected function setUp(): void {
        $this->taskManager = new TaskManager('https://your-jira-instance.com', 'your-username', 'your-password', 'http://your-agent-url');
    }

    public function testCreateTask() {
        $projectId = 1;
        $title = 'Implement PHP Agent';
        $description = 'Create a PHP agent for tracking tasks.';
        $this->taskManager->createTask($projectId, $title, $description);

        // Verificar se o projeto contém a tarefa
        $project = $this->taskManager->findProjectById($projectId);
        $this->assertNotEmpty($project->getTasks());
    }

    public function testUpdateTaskStatus() {
        $taskId = 1;
        $status = 'In Progress';
        $this->taskManager->updateTaskStatus($taskId, $status);

        // Verificar se o status da tarefa foi atualizado
        $task = $this->taskManager->findTaskById($taskId);
        $this->assertEquals('In Progress', $task->getStatus());
    }

    public function testTrackTaskProgress() {
        $taskId = 1;
        $progress = 50;
        $this->taskManager->trackTaskProgress($taskId, $progress);

        // Verificar se a progresso da tarefa foi atualizado
        $task = $this->taskManager->findTaskById($taskId);
        $this->assertEquals(50, $task->getStatus());
    }

    public function testCreateIssue() {
        $projectName = 'My Project';
        $issueType = 'Bug';
        $summary = 'Implement PHP Agent';
        $description = 'Create a PHP agent for tracking tasks.';
        $this->taskManager->createIssue($projectName, $issueType, $summary, $description);

        // Verificar se o issue foi criado em Jira
        // Este é um exemplo fictício e não implementado
        echo "Creating issue in Jira: {$projectName} - {$issueType}\n";
    }
}