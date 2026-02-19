<?php

// Importar as bibliotecas necessárias
require 'vendor/autoload.php';

// Classe para representar um item de atividade
class ActivityItem {
    public $id;
    public $description;
    public $status;

    // Construtor da classe
    public function __construct($id, $description, $status) {
        $this->id = $id;
        $this->description = $description;
        $this->status = $status;
    }

    // Método para exibir as informações do item de atividade
    public function display() {
        echo "ID: {$this->id}\n";
        echo "Descrição: {$this->description}\n";
        echo "Status: {$this->status}\n";
    }
}

// Classe para representar um serviço de atividades
class ActivityService {
    private $items = [];

    // Método para adicionar um item de atividade ao serviço
    public function addItem(ActivityItem $item) {
        $this->items[] = $item;
    }

    // Método para listar todas as atividades do serviço
    public function listItems() {
        foreach ($this->items as $item) {
            echo "Item {$item->id}:\n";
            $item->display();
            echo "\n";
        }
    }
}

// Classe para representar o PHP Agent
class PHPAgent {
    private $service;

    // Construtor da classe
    public function __construct(ActivityService $service) {
        $this->service = $service;
    }

    // Método para enviar uma atividade ao serviço do PHP Agent
    public function sendActivity($activityItem) {
        $this->service->addItem($activityItem);
    }
}

// Função principal
function main() {
    // Criar um serviço de atividades
    $activityService = new ActivityService();

    // Criar um item de atividade
    $activityItem1 = new ActivityItem(1, "Início do projeto", "Planned");
    $activityItem2 = new ActivityItem(2, "Conclusão do projeto", "Completed");

    // Adicionar os itens de atividade ao serviço
    $activityService->addItem($activityItem1);
    $activityService->addItem($activityItem2);

    // Criar um PHP Agent e enviar as atividades
    $phpAgent = new PHPAgent($activityService);
    $phpAgent->sendActivity($activityItem1);
    $phpAgent->sendActivity($activityItem2);
}

// Executar a função principal se o script for executado diretamente
if (__name__ == "__main__") {
    main();
}