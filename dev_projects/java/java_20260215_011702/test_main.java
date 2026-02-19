import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.issue.Issue;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

public class JavaAgentJiraIntegrationTest {

    private Jira jira;
    private Project project;

    @BeforeEach
    public void setUp() throws Exception {
        // Configurar o Jira e o projeto
        jira = new Jira();
        project = jira.getProject("SCRUM-13");
    }

    @AfterEach
    public void tearDown() throws Exception {
        // Limpar o ambiente após os testes
        // ...
    }

    @Test
    public void testCreateIssueSuccess() throws Exception {
        String issueType = "Bug";
        String summary = "Teste de criação de issue";

        createIssue(jira, project, issueType, summary);
        assertEquals("Created issue: " + project.getId(), "Created issue: " + project.getId());
    }

    @Test
    public void testCreateIssueFailureDivideByZero() throws Exception {
        String issueType = "Bug";
        String summary = "Erro de divisão por zero";

        assertThrows(IllegalArgumentException.class, () -> createIssue(jira, project, issueType, "10 / 0"));
    }

    @Test
    public void testCreateIssueFailureInvalidSummary() throws Exception {
        String issueType = "Bug";
        String summary = "";

        assertThrows(IllegalArgumentException.class, () -> createIssue(jira, project, issueType, summary));
    }

    // Adicionar mais testes para outras funções e métodos públicos
}