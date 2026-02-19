import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraManager;
import com.atlassian.jira.plugin.system.SystemPlugin;
import com.atlassian.jira.user.User;
import com.atlassian.jira.util.JiraUtils;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

public class JavaAgentJiraIntegratorTest {

    private Jira jira;
    private JiraManager jiraManager;
    private User user;

    @BeforeEach
    public void setUp() {
        String jiraUrl = "http://localhost:8080";
        String username = "admin";
        String password = "admin";

        try {
            // Conecta ao Jira
            jira = new Jira(jiraUrl, username, password);
            jiraManager = JiraUtils.getJiraManager(jira);

            // Cria um novo usuário para testes
            user = systemPlugin.getUserByName("testuser");
            jiraManager.createUser(user, "Test User", "password");

        } catch (Exception e) {
            fail("Failed to set up environment: " + e.getMessage());
        }
    }

    @AfterEach
    public void tearDown() {
        try {
            // Limpa o ambiente após os testes
            jiraManager.deleteUser(user);
        } catch (Exception e) {
            System.out.println("Failed to clean up environment: " + e.getMessage());
        }
    }

    @Test
    public void testCreateTicket() throws Exception {
        String summary = "New Java Agent Integration";
        String description = "This is a test ticket for the Java Agent integration in Jira.";

        createTicket(jiraManager, summary, description);

        // Verifica se o ticket foi criado corretamente
        int issueKey = jiraManager.getIssueKey(summary);
        assertTrue("Ticket not created", issueKey != -1);
    }

    @Test
    public void testUpdateTicket() throws Exception {
        String issueKey = "TEST-1";
        String updatedDescription = "This is an updated test ticket for the Java Agent integration in Jira.";

        updateTicket(jiraManager, issueKey, updatedDescription);

        // Verifica se o ticket foi atualizado corretamente
        Issue issue = jiraManager.getIssue(issueKey);
        assertEquals("Updated description", updatedDescription, issue.getDescription());
    }

    @Test
    public void testMonitorMetricsAndLogs() throws Exception {
        // Implemente a lógica para monitorar real-time de métricas e logs
        System.out.println("Monitoring metrics and logs...");
    }

    @Test
    public void testManageTasksAndProjects() throws Exception {
        // Implemente a lógica para gerenciamento de tarefas e projetos em Jira
        System.out.println("Managing tasks and projects...");
    }
}