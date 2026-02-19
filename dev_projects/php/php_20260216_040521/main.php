<?php

// Importar bibliotecas necessárias
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
        $this->status = 'Open';
    }

    // Getters e setters
    public function getId() {
        return $this->id;
    }

    public function setId($id) {
        $this->id = $id;
    }

    public function getTitle() {
        return $this->title;
    }

    public function setTitle($title) {
        $this->title = $title;
    }

    public function getDescription() {
        return $this->description;
    }

    public function setDescription($description) {
        $this->description = $description;
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

    // Getters e setters
    public function getId() {
        return $this->id;
    }

    public function setId($id) {
        $this->id = $id;
    }

    public function getName() {
        return $this->name;
    }

    public function setName($name) {
        $this->name = $name;
    }
}

// Classe para representar uma atividade
class Activity {
    private $id;
    private $taskId;
    private $userId;
    private $activityType;

    public function __construct($id, $taskId, $userId, $activityType) {
        $this->id = $id;
        $this->taskId = $taskId;
        $this->userId = $userId;
        $this->activityType = $activityType;
    }

    // Getters e setters
    public function getId() {
        return $this->id;
    }

    public function setId($id) {
        $this->id = $id;
    }

    public function getTaskId() {
        return $this->taskId;
    }

    public function setTaskId($taskId) {
        $this->taskId = $taskId;
    }

    public function getUserId() {
        return $this->userId;
    }

    public function setUserId($userId) {
        $this->userId = $userId;
    }

    public function getActivityType() {
        return $this->activityType;
    }

    public function setActivityType($activityType) {
        $this->activityType = $activityType;
    }
}

// Classe para representar o sistema de atividades
class ActivityTracker {
    private $tasks = [];
    private $users = [];
    private $activities = [];

    // Função para adicionar uma tarefa
    public function addTask($task) {
        if (!in_array($task, $this->tasks)) {
            $this->tasks[] = $task;
        }
    }

    // Função para adicionar um usuário
    public function addUser($user) {
        if (!in_array($user, $this->users)) {
            $this->users[] = $user;
        }
    }

    // Função para adicionar uma atividade
    public function addActivity($activity) {
        if (!in_array($activity, $this->activities)) {
            $this->activities[] = $activity;
        }
    }

    // Função para listar todas as tarefas
    public function listTasks() {
        return $this->tasks;
    }

    // Função para listar todos os usuários
    public function listUsers() {
        return $this->users;
    }

    // Função para listar todas as atividades
    public function listActivities() {
        return $this->activities;
    }
}

// Classe para representar o sistema de monitoramento
class ActivityMonitor {
    private $activityTracker;

    public function __construct(ActivityTracker $activityTracker) {
        $this->activityTracker = $activityTracker;
    }

    // Função para monitorar atividades
    public function monitorActivities() {
        foreach ($this->activityTracker->listActivities() as $activity) {
            echo "Activity ID: {$activity->getId()}, Task ID: {$activity->getTaskId()}, User ID: {$activity->getUserId()}, Activity Type: {$activity-> getActivityType()}\n";
        }
    }
}

// Classe para representar o sistema de gerenciamento
class ActivityManager {
    private $activityTracker;
    private $activityMonitor;

    public function __construct(ActivityTracker $activityTracker, ActivityMonitor $activityMonitor) {
        $this->activityTracker = $activityTracker;
        $this->activityMonitor = $activityMonitor;
    }

    // Função para gerenciar tarefas
    public function manageTasks() {
        foreach ($this->activityTracker->listTasks() as $task) {
            echo "Task ID: {$task->getId()}, Title: {$task->getTitle()}, Description: {$task->getDescription()}, Status: {$task->getStatus()}\n";
        }
    }

    // Função para gerenciar usuários
    public function manageUsers() {
        foreach ($this->activityTracker->listUsers() as $user) {
            echo "User ID: {$user->getId()}, Name: {$user->getName()}\n";
        }
    }

    // Função para gerenciar atividades
    public function manageActivities() {
        foreach ($this->activityTracker->listActivities() as $activity) {
            echo "Activity ID: {$activity->getId()}, Task ID: {$activity->getTaskId()}, User ID: {$activity->getUserId()}, Activity Type: {$activity-> getActivityType()}\n";
        }
    }
}

// Classe para representar o sistema de relatórios
class ActivityReport {
    private $activityTracker;

    public function __construct(ActivityTracker $activityTracker) {
        $this->activityTracker = $activityTracker;
    }

    // Função para gerar relatório detalhado
    public function generateReport() {
        echo "Activity Report:\n";
        foreach ($this->activityTracker->listActivities() as $activity) {
            echo "Activity ID: {$activity->getId()}, Task ID: {$activity->getTaskId()}, User ID: {$activity->getUserId()}, Activity Type: {$activity-> getActivityType()}\n";
        }
    }
}

// Função principal
function main() {
    // Criar um sistema de atividades
    $activityTracker = new ActivityTracker();

    // Criar um usuário
    $user1 = new User(1, 'John Doe');
    $activityTracker->addUser($user1);

    // Criar uma tarefa
    $task1 = new Task(1, 'Task 1', 'Description of task 1');
    $activityTracker->addTask($task1);

    // Criar uma atividade
    $activity1 = new Activity(1, 1, 1, 'Completed');
    $activityTracker->addActivity($activity1);

    // Criar um monitor de atividades
    $activityMonitor = new ActivityMonitor($activityTracker);

    // Monitorar atividades
    $activityMonitor->monitorActivities();

    // Criar um gerenciador de tarefas
    $taskManager = new ActivityManager($activityTracker, $activityMonitor);

    // Gerenciar tarefas
    $taskManager->manageTasks();

    // Criar um gerenciador de usuários
    $userManager = new ActivityManager($activityTracker, $activityMonitor);

    // Gerenciar usuários
    $userManager->manageUsers();

    // Criar um gerenciador de atividades
    $activityManager = new ActivityManager($activityTracker, $activityMonitor);

    // Gerenciar atividades
    $activityManager->manageActivities();

    // Criar um relatório detalhado
    $activityReport = new ActivityReport($activityTracker);
    $activityReport->generateReport();
}

// Executar o programa principal
main();