import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class JavaAgentTest {

    @Test
    public void testCreateProject() throws IOException {
        // Configuração do Jira
        Jira jira = new Jira("http://localhost:8080", "admin", "password");

        // Criação de um novo projeto com valores válidos
        Project project = createProject(jira, "MyProject");
        assertNotNull(project);
        assertEquals("MyProject", project.getName());
    }

    @Test
    public void testCreateIssue() throws IOException {
        // Configuração do Jira
        Jira jira = new Jira("http://localhost:8080", "admin", "password");

        // Criação de uma nova tarefa com valores válidos
        Issue issue = createIssue(jira, null, "Task 1", "This is a test task.");
        assertNotNull(issue);
    }

    @Test
    public void testConfigureJavaAgent() throws IOException {
        // Configuração do Jira
        Jira jira = new Jira("http://localhost:8080", "admin", "password");

        // Criação de uma nova tarefa com valores válidos
        Issue issue = createIssue(jira, null, "Task 1", "This is a test task.");
        configureJavaAgent(jira, issue);
    }

    private static Project createProject(Jira jira, String projectName) throws IOException {
        JiraServiceContext serviceContext = new JiraServiceContext("admin", "password");
        return jira.createProject(serviceContext, projectName);
    }

    private static Issue createIssue(Jira jira, Project project, String summary, String description) throws IOException {
        FieldManager fieldManager = jira.getFieldManager();
        CustomFieldManager customFieldManager = jira.getCustomFieldManager();

        SelectField statusField = customFieldManager.getSelectFieldByName("Status");
        TextField summaryField = fieldManager.getTextFieldByName("Summary");

        Issue issue = jira.createIssue(serviceContext, project.getKey(), "Task 1", description);
        issue.setFieldValue(summaryField, summary);
        issue.setFieldValue(statusField, "To Do");

        return issue;
    }

    private static void configureJavaAgent(Jira jira, Issue issue) throws IOException {
        // Simulação de configuração do Java Agent
        String agentUrl = "http://localhost:8081/agent";
        HttpClient client = HttpClient.newHttpClient();
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(agentUrl))
                .POST(HttpRequest.BodyPublishers.ofString("issueKey=" + issue.getKey()))
                .build();

        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
        System.out.println("Configuração do Java Agent concluída: " + response.body());
    }
}