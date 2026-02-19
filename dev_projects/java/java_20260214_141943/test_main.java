import com.atlassian.jira.Jira;
import com.atlassian.jira.client.api.JiraClientBuilder;
import com.atlassian.jira.client.api.RestException;

public class JavaAgentTest {
    private static final String JIRA_URL = "http://your-jira-url";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    @org.junit.Test
    public void testCreateTaskWithValidValues() throws RestException {
        try (JiraRestClient client = new JiraClientBuilder(JIRA_URL).user(USERNAME).password(PASSWORD).build()) {
            createTask(client);
        }
    }

    @org.junit.Test(expected = IllegalArgumentException.class)
    public void testCreateTaskWithInvalidValueForTitle() throws RestException {
        try (JiraRestClient client = new JiraClientBuilder(JIRA_URL).user(USERNAME).password(PASSWORD).build()) {
            createTask(client, " ");
        }
    }

    @org.junit.Test(expected = IllegalArgumentException.class)
    public void testCreateTaskWithInvalidValueForDescription() throws RestException {
        try (JiraRestClient client = new JiraClientBuilder(JIRA_URL).user(USERNAME).password(PASSWORD).build()) {
            createTask(client, " ");
        }
    }

    private static void createTask(JiraRestClient client) throws RestException {
        // Implementar a lógica para criar uma tarefa em Jira
        // Por exemplo, usando o Jira REST API
        // Aqui você pode usar o client para fazer chamadas à API do Jira
    }

    private static void createTask(JiraRestClient client, String title, String description) throws RestException {
        // Implementar a lógica para criar uma tarefa em Jira
        // Por exemplo, usando o Jira REST API
        // Aqui você pode usar o client para fazer chamadas à API do Jira
    }
}