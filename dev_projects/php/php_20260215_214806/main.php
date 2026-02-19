<?php

// Importar as bibliotecas necessárias
require 'vendor/autoload.php';

// Classe para representar uma tarefa
class Task {
    private $id;
    private $title;
    private $description;
    private $status;

    public function __construct($id, $title, $description) {
        $this->id = $id;
        $this->title = $title;
        $this->description = $description;
        $this->status = 'Pending';
    }

    public function getId() {
        return $this->id;
    }

    public function getTitle() {
        return $this->title;
    }

    public function getDescription() {
        return $this->description;
    }

    public function getStatus() {
        return $this->status;
    }

    public function setStatus($status) {
        $this->status = $status;
    }
}

// Classe para representar um usuário
class User {
    private $id;
    private $name;

    public function __construct($id, $name) {
        $this->id = $id;
        $this->name = $name;
    }

    public function getId() {
        return $this->id;
    }

    public function getName() {
        return $this->name;
    }
}

// Classe para representar um projeto
class Project {
    private $id;
    private $title;

    public function __construct($id, $title) {
        $this->id = $id;
        $this->title = $title;
    }

    public function getId() {
        return $this->id;
    }

    public function getTitle() {
        return $this->title;
    }
}

// Classe para representar uma atividade
class Activity {
    private $id;
    private $taskId;
    private $userId;
    private $projectId;
    private $description;
    private $status;

    public function __construct($id, $taskId, $userId, $projectId, $description) {
        $this->id = $id;
        $this->taskId = $taskId;
        $this->userId = $userId;
        $this->projectId = $projectId;
        $this->description = $description;
        $this->status = 'Pending';
    }

    public function getId() {
        return $this->id;
    }

    public function getTaskId() {
        return $this->taskId;
    }

    public function getUserId() {
        return $this->userId;
    }

    public function getProjectId() {
        return $this->projectId;
    }

    public function getDescription() {
        return $this->description;
    }

    public function getStatus() {
        return $this->status;
    }

    public function setStatus($status) {
        $this->status = $status;
    }
}

// Classe para representar o sistema de atividades
class ActivitySystem {
    private $tasks;
    private $users;
    private $projects;

    public function __construct() {
        $this->tasks = [];
        $this->users = [];
        $this->projects = [];
    }

    public function addTask(Task $task) {
        $this->tasks[] = $task;
    }

    public function addUser(User $user) {
        $this->users[] = $user;
    }

    public function addProject(Project $project) {
        $this->projects[] = $project;
    }

    public function getActivity($taskId, $userId, $projectId) {
        foreach ($this->tasks as $task) {
            if ($task->getId() === $taskId && $task->getUserId() === $userId && $task->getProjectId() === $projectId) {
                return $task;
            }
        }

        return null;
    }

    public function updateActivity(Activity $activity) {
        foreach ($this->tasks as &$task) {
            if ($task->getId() === $activity->getId()) {
                $task->setTitle($activity->getTitle());
                $task->setDescription($activity->getDescription());
                $task->setStatus($activity->getStatus());
                break;
            }
        }
    }

    public function deleteActivity(Activity $activity) {
        foreach ($this->tasks as &$task) {
            if ($task->getId() === $activity->getId()) {
                array_splice($this->tasks, array_search($task, $this->tasks), 1);
                break;
            }
        }
    }

    public function getTasksByUser(User $user) {
        return array_filter($this->tasks, function ($task) use ($user) {
            return $task->getUserId() === $user->getId();
        });
    }

    public function getTasksByProject(Project $project) {
        return array_filter($this->tasks, function ($task) use ($project) {
            return $task->getProjectId() === $project->getId();
        });
    }
}

// Classe para representar o sistema de atividades com integração com Jira
class ActivitySystemWithJira extends ActivitySystem {
    private $jiraClient;

    public function __construct($jiraClient) {
        parent::__construct();
        $this->jiraClient = $jiraClient;
    }

    public function addTaskToJira(Task $task) {
        // Implementar a lógica para adicionar uma tarefa ao Jira
        // Exemplo: $this->jiraClient->addIssue($task);
    }

    public function updateActivityInJira(Activity $activity) {
        // Implementar a lógica para atualizar uma atividade no Jira
        // Exemplo: $this->jiraClient->updateIssue($activity);
    }

    public function deleteTaskFromJira(Task $task) {
        // Implementar a lógica para deletar uma tarefa do Jira
        // Exemplo: $this->jiraClient->deleteIssue($task);
    }
}

// Função principal
function main() {
    // Criar instâncias de classes
    $activitySystem = new ActivitySystem();
    $user1 = new User(1, 'John Doe');
    $project1 = new Project(1, 'Project A');

    // Adicionar tarefas ao sistema
    $task1 = new Task(1, 'Implement feature X', 'Implement the feature X in the project.');
    $activitySystem->addTask($task1);
    $activitySystem->addUser($user1);
    $activitySystem->addProject($project1);

    // Adicionar atividade ao sistema
    $activity = new Activity(1, 1, 1, 1, 'Implement feature X', 'Implement the feature X in the project.');
    $activitySystem->addActivity($activity);

    // Exibir tarefas do usuário
    $tasksByUser = $activitySystem->getTasksByUser($user1);
    foreach ($tasksByUser as $task) {
        echo "Task ID: {$task->getId()}, Title: {$task->getTitle()}\n";
    }

    // Exibir atividades do projeto
    $activitiesByProject = $activitySystem->getTasksByProject($project1);
    foreach ($activitiesByProject as $activity) {
        echo "Activity ID: {$activity->getId()}, Description: {$activity->getDescription()}\n";
    }
}

// Executar o código principal
if (__name__ == "__main__") {
    main();
}