<?php

// Importar as bibliotecas necessárias
require 'vendor/autoload.php';

// Classe PHP Agent para Jira
class PhpAgentJira
{
    private $jiraUrl;
    private $username;
    private $password;

    public function __construct($jiraUrl, $username, $password)
    {
        $this->jiraUrl = $jiraUrl;
        $this->username = $username;
        $this->password = $password;
    }

    // Função para criar uma tarefa no Jira
    public function createTask($issueKey, $summary, $description)
    {
        $url = $this->jiraUrl . '/rest/api/2/issue';
        $headers = [
            'Content-Type: application/json',
            'Authorization: Basic ' . base64_encode("$this->username:$this->password")
        ];

        $data = [
            'fields' => [
                'project' => ['key' => 'YOUR_PROJECT_KEY'],
                'summary' => $summary,
                'description' => $description
            ]
        ];

        $response = file_get_contents($url, false, stream_context_create([
            'http' => [
                'method' => 'POST',
                'header' => implode("\r\n", $headers),
                'content' => json_encode($data)
            ]
        ]));

        if ($response === false) {
            throw new Exception('Failed to create task');
        }

        return json_decode($response, true);
    }
}

// Função para executar o script
function main()
{
    // Configurações do PHP Agent Jira
    $jiraUrl = 'https://your-jira-instance.atlassian.net';
    $username = 'your-username';
    $password = 'your-password';

    // Instancia da classe PHP Agent Jira
    $agentJira = new PhpAgentJira($jiraUrl, $username, $password);

    // Título e descrição da tarefa
    $issueKey = 'YOUR_TASK_KEY';
    $summary = 'Task summary';
    $description = 'Task description';

    try {
        // Cria a tarefa no Jira
        $task = $agentJira->createTask($issueKey, $summary, $description);

        echo "Task created successfully:\n";
        print_r($task);
    } catch (Exception $e) {
        echo "Error: " . $e->getMessage();
    }
}

// Executar o script
if (__name__ == "__main__") {
    main();
}