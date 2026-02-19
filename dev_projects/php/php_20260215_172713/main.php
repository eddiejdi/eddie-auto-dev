<?php

// Importar as bibliotecas necessárias
require 'vendor/autoload.php';

use PhpOffice\PhpSpreadsheet\Spreadsheet;
use PhpOffice\PhpSpreadsheet\Writer\Xlsx;

class JiraIntegration {
    private $jiraUrl;
    private $username;
    private $password;
    private $spreadsheet;

    public function __construct($jiraUrl, $username, $password) {
        $this->jiraUrl = $jiraUrl;
        $this->username = $username;
        $this->password = $password;
        $this->spreadsheet = new Spreadsheet();
        $this->createSheet('Tasks');
    }

    private function createSheet($title) {
        $worksheet = $this->spreadsheet->getActiveSheet();
        $worksheet->setTitle($title);
        // Adicionar cabeçalhos da planilha
        $headers = ['Task ID', 'Title', 'Status', 'Assignee'];
        foreach ($headers as $header) {
            $worksheet->setCellValueByColumnAndRow(1, 1 + array_search($header, $headers), $header);
        }
    }

    public function addTask($title, $status, $assignee) {
        $row = $this->spreadsheet->getActiveSheet()->getLastRow() + 1;
        $worksheet = $this->spreadsheet->getActiveSheet();
        $worksheet->setCellValueByColumnAndRow(1, $row, $title);
        $worksheet->setCellValueByColumnAndRow(2, $row, $status);
        $worksheet->setCellValueByColumnAndRow(3, $row, $assignee);

        // Salvar a planilha em um arquivo Excel
        $writer = new Xlsx($this->spreadsheet);
        $writer->save('tasks.xlsx');
    }
}

class Task {
    private $id;
    private $title;
    private $status;
    private $assignee;

    public function __construct($id, $title, $status, $assignee) {
        $this->id = $id;
        $this->title = $title;
        $this->status = $status;
        $this->assignee = $assignee;
    }

    public function getId() {
        return $this->id;
    }

    public function getTitle() {
        return $this->title;
    }

    public function getStatus() {
        return $this->status;
    }

    public function getAssignee() {
        return $this->assignee;
    }
}

class TaskTracker {
    private $jiraIntegration;

    public function __construct($jiraUrl, $username, $password) {
        $this->jiraIntegration = new JiraIntegration($jiraUrl, $username, $password);
    }

    public function addTask($title, $status, $assignee) {
        // Simulação de captura de dados de atividade
        $task = new Task(null, $title, $status, $assignee);

        // Adicionar a tarefa ao Jira
        $this->jiraIntegration->addTask($task->getTitle(), $task->getStatus(), $task->getAssignee());

        return $task;
    }
}

// Exemplo de uso do TaskTracker
if (php_sapi_name() === 'cli') {
    $taskTracker = new TaskTracker('https://your-jira-instance.atlassian.net', 'username', 'password');
    $task = $taskTracker->addTask('Implement SCRUM-15 in PHP', 'In Progress', 'John Doe');
    echo "Task added successfully: ID {$task->getId()}, Title: {$task->getTitle()}, Status: {$task->getStatus()}, Assignee: {$task->getAssignee()}";
}