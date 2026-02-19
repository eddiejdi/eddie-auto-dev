<?php

// Importar bibliotecas necessárias
require 'vendor/autoload.php';

// Classe para representar um evento
class Event {
    public $timestamp;
    public $type;
    public $data;

    public function __construct($timestamp, $type, $data) {
        $this->timestamp = $timestamp;
        $this->type = $type;
        $this->data = $data;
    }
}

// Classe para representar um registro de evento
class EventLog {
    private $events;

    public function __construct() {
        $this->events = [];
    }

    public function logEvent(Event $event) {
        $this->events[] = $event;
    }

    public function getEvents() {
        return $this->events;
    }
}

// Classe para representar um monitorador de atividades
class ActivityMonitor {
    private $log;

    public function __construct() {
        $this->log = new EventLog();
    }

    public function trackActivity($event) {
        $timestamp = time();
        $this->log->logEvent(new Event($timestamp, 'activity', $event));
    }

    public function getEvents() {
        return $this->log->getEvents();
    }
}

// Classe para representar um PHP Agent
class PhpAgent {
    private $monitor;

    public function __construct(ActivityMonitor $monitor) {
        $this->monitor = $monitor;
    }

    public function trackActivity($event) {
        $timestamp = time();
        $this->monitor->trackActivity($event);
    }
}

// Função principal
function main() {
    // Criar um monitor de atividades
    $monitor = new ActivityMonitor();

    // Criar um PHP Agent e passar o monitor para ele
    $phpAgent = new PhpAgent($monitor);

    // Simular atividade no sistema
    $phpAgent->trackActivity('User logged in');

    // Exibir eventos registrados
    $events = $monitor->getEvents();
    foreach ($events as $event) {
        echo "Timestamp: {$event->timestamp}, Type: {$event->type}, Data: {$event->data}\n";
    }
}

// Executar a função principal
if (__name__ == "__main__") {
    main();
}