import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class JiraIntegrationTest {

    private JiraClient client;

    @BeforeEach
    public void setUp() {
        // Configuração do Jira Client
        String jiraUrl = "https://your-jira-instance.com";
        String username = "your-username";
        String password = "your-password";

        try (JiraClientBuilder builder = new JiraClientBuilder(jiraUrl).basicAuth(username, password)) {
            client = builder.build();
        } catch (JiraException e) {
            fail("Error connecting to Jira: " + e.getMessage());
        }
    }

    @Test
    public void testCreateIssueSuccess() throws JiraException {
        // Definição do título da tarefa
        String issueTitle = "Teste de Integração com Java Agent";

        // Definição do corpo da tarefa
        String issueDescription = "Este é um teste para integração do Java Agent com Jira.";

        // Criação da tarefa no Jira
        client.createIssue(issueTitle, issueDescription);

        // Verificação se a tarefa foi criada corretamente
        assertNotNull(client.getIssue(issueTitle));
    }

    @Test
    public void testCreateIssueFailure() {
        // Definição do título da tarefa (divisão por zero)
        String issueTitle = "Divisão por Zero";

        // Definição do corpo da tarefa
        String issueDescription = "Este é um teste para integração do Java Agent com Jira.";

        try {
            client.createIssue(issueTitle, issueDescription);
            fail("Expected an exception to be thrown for division by zero");
        } catch (JiraException e) {
            // Verificação se a exceção foi lançada corretamente
            assertEquals("Error creating issue: java.lang.ArithmeticException", e.getMessage());
        }
    }

    @Test
    public void testCreateIssueEdgeCase() {
        // Definição do título da tarefa (string vazia)
        String issueTitle = "";

        // Definição do corpo da tarefa
        String issueDescription = "Este é um teste para integração do Java Agent com Jira.";

        try {
            client.createIssue(issueTitle, issueDescription);
            fail("Expected an exception to be thrown for empty title");
        } catch (JiraException e) {
            // Verificação se a exceção foi lançada corretamente
            assertEquals("Error creating issue: java.lang.IllegalArgumentException", e.getMessage());
        }
    }
}