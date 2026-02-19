<?php

use PHPUnit\Framework\TestCase;

class PHPAgentTest extends TestCase {
    public function testTrackActivitySuccess() {
        // URL do PHP Agent e token de autenticação
        $url = 'https://your-php-agent-url.com/api/v1/issue';
        $token = 'YOURPHPAGENTTOKEN';

        // Criar uma instância da classe PHPAgent
        $agent = new PHPAgent($url, $token);

        // Atividade a ser registrada
        $activity = "Novo issue criado: {$argv[1]}";

        // Registrar a atividade no Jira
        $result = $agent->trackActivity($activity);

        // Verificar se a requisição foi bem-sucedida
        $this->assertNotEmpty($result);
    }

    public function testTrackActivityFailure() {
        // URL do PHP Agent e token de autenticação
        $url = 'https://your-php-agent-url.com/api/v1/issue';
        $token = 'YOURPHPAGENTTOKEN';

        // Criar uma instância da classe PHPAgent
        $agent = new PHPAgent($url, $token);

        // Atividade a ser registrada
        $activity = "Novo issue criado: {$argv[1]}";

        // Registrar a atividade no Jira com um token inválido
        try {
            $result = $agent->trackActivity($activity);
        } catch (Exception $e) {
            $this->assertEquals('Failed to track activity: ' . curl_error($ch), $e->getMessage());
        }
    }

    public function testTrackActivityEdgeCases() {
        // URL do PHP Agent e token de autenticação
        $url = 'https://your-php-agent-url.com/api/v1/issue';
        $token = 'YOURPHPAGENTTOKEN';

        // Criar uma instância da classe PHPAgent
        $agent = new PHPAgent($url, $token);

        // Atividade a ser registrada com um valor inválido para o campo summary
        try {
            $result = $agent->trackActivity("Novo issue criado: {$argv[1]}");
        } catch (Exception $e) {
            $this->assertEquals('Failed to track activity: ' . curl_error($ch), $e->getMessage());
        }
    }
}