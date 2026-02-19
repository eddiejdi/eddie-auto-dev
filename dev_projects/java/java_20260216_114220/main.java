import com.atlassian.jira.client.api.JiraClient;
import com.atlassian.jira.client.api.JiraClientBuilder;
import com.atlassian.jira.client.api.JiraException;

public class JiraIntegration {

    public static void main(String[] args) {
        // Configuração do Jira Client
        String jiraUrl = "https://your-jira-instance.com";
        String username = "your-username";
        String password = "your-password";

        try (JiraClient client = new JiraClientBuilder(jiraUrl).basicAuth(username, password).build()) {

            // Exemplo de função para criar uma tarefa no Jira
            createIssue(client);

        } catch (JiraException e) {
            System.err.println("Error connecting to Jira: " + e.getMessage());
        }
    }

    private static void createIssue(JiraClient client) throws JiraException {
        // Definição do título da tarefa
        String issueTitle = "Teste de Integração com Java Agent";

        // Definição do corpo da tarefa
        String issueDescription = "Este é um teste para integração do Java Agent com Jira.";

        // Criação da tarefa no Jira
        client.createIssue(issueTitle, issueDescription);
    }
}