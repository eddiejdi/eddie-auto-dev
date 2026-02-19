use PhpAgent\Agent;
use PHPUnit\Framework\TestCase;

class PhpAgentTest extends TestCase
{
    public function testSendLogToJiraSuccess()
    {
        $agent = new Agent([
            'host' => 'localhost',
            'port' => 8080,
        ]);

        $body = [
            'issue' => [
                'fields' => [
                    'summary' => 'Novo Log',
                    'description' => 'Teste de log enviado via PHP Agent',
                ],
            ],
        ];

        try {
            $response = $agent->post('rest/api/2/issue', json_encode($body));
            $this->assertEquals("Log enviado com sucesso: " . $response, $response);
        } catch (\Exception $e) {
            $this->fail("Erro ao enviar log para Jira: " . $e->getMessage());
        }
    }

    public function testSendLogToJiraError()
    {
        $agent = new Agent([
            'host' => 'localhost',
            'port' => 8080,
        ]);

        try {
            $response = $agent->post('rest/api/2/issue', json_encode(['invalid' => 'data']));
            $this->fail("Erro esperado ao enviar log para Jira");
        } catch (\Exception $e) {
            $this->assertEquals("Erro ao enviar log para Jira", $e->getMessage());
        }
    }

    public function testSendLogToJiraEdgeCase()
    {
        $agent = new Agent([
            'host' => 'localhost',
            'port' => 8080,
        ]);

        try {
            $response = $agent->post('rest/api/2/issue', json_encode(['summary' => '', 'description' => '']));
            $this->assertEquals("Log enviado com sucesso: " . $response, $response);
        } catch (\Exception $e) {
            $this->fail("Erro esperado ao enviar log para Jira");
        }
    }
}