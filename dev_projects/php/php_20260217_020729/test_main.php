<?php

use PhpAgent\JiraClient;
use PhpAgent\Task;

class JiraScrum15Test extends PHPUnit\Framework\TestCase {

    public function setUp(): void {
        // Configuração do Jira
        $this->url = 'https://your-jira-instance.atlassian.net';
        $this->username = 'your-username';
        $this->password = 'your-password';

        // Criar uma instância da classe JiraScrum15
        $this->jiraScrum15 = new JiraScrum15($this->url, $this->username, $this->password);
    }

    public function testMonitorarAtividades() {
        // Caso de sucesso com valores válidos
        $tasks = [
            ['title' => 'Task 1', 'status' => 'To Do', 'priority' => 'Low'],
            ['title' => 'Task 2', 'status' => 'In Progress', 'priority' => 'High']
        ];

        // Simular o retorno da API
        $this->mockJiraClient($tasks);

        $result = $this->jiraScrum15->monitorarAtividades();

        foreach ($result as $task) {
            $this->assertEquals($task['title'], $tasks[0]['title']);
            $this->assertEquals($task['status'], $tasks[0]['status']);
            $this->assertEquals($task['priority'], $tasks[0]['priority']);
        }
    }

    public function testGerenciarTarefas() {
        // Caso de sucesso com valores válidos
        $taskId = '1234';
        $status = 'In Progress';
        $priority = 'High';

        // Simular o retorno da API
        $this->mockJiraClient([
            ['key' => $taskId, 'title' => 'Task 1', 'status' => 'To Do', 'priority' => 'Low']
        ]);

        $updatedTask = new Task(
            $taskId,
            $status,
            $priority
        );

        $this->jiraScrum15->gerenciarTarefas($taskId, $status, $priority);

        // Verificar se a tarefa foi atualizada corretamente
        $task = $this->mockJiraClient([
            ['key' => $taskId, 'title' => 'Task 1', 'status' => 'In Progress', 'priority' => 'High']
        ]);

        $this->assertEquals($task[0]['status'], $updatedTask->getStatus());
    }

    public function testGerenciarTarefasErro() {
        // Caso de erro (divisão por zero)
        $taskId = '1234';
        $status = 'In Progress';
        $priority = 'High';

        // Simular o retorno da API com um erro
        $this->mockJiraClient([
            ['key' => $taskId, 'title' => 'Task 1', 'status' => 'To Do', 'priority' => 'Low']
        ]);

        try {
            $this->jiraScrum15->gerenciarTarefas($taskId, $status, $priority);
            $this->fail('Deveria haver um erro');
        } catch (Exception $e) {
            $this->assertEquals($e->getMessage(), 'Erro ao gerenciar tarefas: Erro ao obter tarefa.');
        }
    }

    private function mockJiraClient(array $tasks) {
        $this->mock = new ReflectionMocker();
        $this->mock->setAccessible(true);

        // Simular a chamada à API
        $this->mock->expects($this->once())
            ->method('getTasks')
            ->willReturn($tasks);

        // Simular a chamada à API para obter uma tarefa específica
        $this->mock->expects($this->once())
            ->method('getTask')
            ->with($taskId)
            ->willReturn(new Task(
                $taskId,
                'Task 1',
                'To Do',
                'Low'
            ));

        // Simular a chamada à API para atualizar uma tarefa
        $this->mock->expects($this->once())
            ->method('updateTask')
            ->with(new Task(
                $taskId,
                $status,
                $priority
            ))
            ->willReturn(true);

        // Instanciar o objeto JiraScrum15 com a mock
        $this->jiraScrum15 = new JiraScrum15($this->url, $this->username, $this->password);
    }
}