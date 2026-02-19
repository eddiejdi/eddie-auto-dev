<?php

// Importar as bibliotecas necessárias
require 'vendor/autoload.php';

// Definir a classe PHP Agent
class PHPAgent {
    private $url;
    private $token;

    public function __construct($url, $token) {
        $this->url = $url;
        $this->token = $token;
    }

    public function trackActivity($activity) {
        try {
            // Montar o payload com os dados da atividade
            $payload = [
                'issue' => [
                    'key' => 'YOURISSUEKEY',
                    'fields' => [
                        'summary' => $activity,
                        'status' => ['name' => 'In Progress']
                    ]
                ]
            ];

            // Criar a requisição POST
            $ch = curl_init();
            curl_setopt($ch, CURLOPT_URL, $this->url);
            curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
            curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($payload));
            curl_setopt($ch, CURLOPT_HTTPHEADER, [
                'Content-Type: application/json',
                'Authorization: Bearer ' . $this->token
            ]);

            // Executar a requisição
            $response = curl_exec($ch);
            curl_close($ch);

            // Verificar se a requisição foi bem-sucedida
            if ($response === false) {
                throw new Exception('Failed to track activity: ' . curl_error($ch));
            }

            return json_decode($response, true);
        } catch (Exception $e) {
            echo "Error tracking activity: " . $e->getMessage();
            return null;
        }
    }
}

// Função principal
function main() {
    // URL do PHP Agent e token de autenticação
    $url = 'https://your-php-agent-url.com/api/v1/issue';
    $token = 'YOURPHPAGENTTOKEN';

    // Criar uma instância da classe PHPAgent
    $agent = new PHPAgent($url, $token);

    // Atividade a ser registrada
    $activity = "Novo issue criado: {$argv[1]}";

    // Registrar a atividade no Jira
    $result = $agent->trackActivity($activity);

    if ($result) {
        echo "Activity tracked successfully: " . json_encode($result);
    }
}

// Executar o script se for CLI
if (php_sapi_name() === 'cli') {
    main();
}