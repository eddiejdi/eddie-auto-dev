import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class JavaAgentJiraIntegrationTest {

    @Test
    public void testCreateProjectSuccess() throws Exception {
        // Configuração do Jira (substitua pelos valores corretos)
        String jiraUrl = "http://your-jira-url";
        String username = "your-username";
        String password = "your-password";

        try {
            // Inicializa o Jira
            Jira jira = new Jira(jiraUrl, username, password);

            // Cria um novo projeto (substitua pelos valores corretos)
            Project project = jira.createProject("My Project", "My Project Description");

            assertNotNull(project);
            assertEquals("My Project", project.getName());
        } catch (JiraException e) {
            fail("Failed to create project: " + e.getMessage());
        }
    }

    @Test
    public void testCreateProjectFailure() throws Exception {
        // Configuração do Jira (substitua pelos valores corretos)
        String jiraUrl = "http://your-jira-url";
        String username = "your-username";
        String password = "your-password";

        try {
            // Inicializa o Jira
            Jira jira = new Jira(jiraUrl, username, password);

            // Tenta criar um projeto com valores inválidos (exemplo: nome vazio)
            Project project = jira.createProject("", "My Project Description");

            assertNull(project);
        } catch (JiraException e) {
            assertEquals("Invalid project name", e.getMessage());
        }
    }

    @Test
    public void testCreateProjectEdgeCase() throws Exception {
        // Configuração do Jira (substitua pelos valores corretos)
        String jiraUrl = "http://your-jira-url";
        String username = "your-username";
        String password = "your-password";

        try {
            // Inicializa o Jira
            Jira jira = new Jira(jiraUrl, username, password);

            // Tenta criar um projeto com nome muito longo (exemplo: 200 caracteres)
            Project project = jira.createProject("a".repeat(200), "My Project Description");

            assertNotNull(project);
            assertEquals("My Project", project.getName());
        } catch (JiraException e) {
            fail("Failed to create project with long name: " + e.getMessage());
        }
    }
}