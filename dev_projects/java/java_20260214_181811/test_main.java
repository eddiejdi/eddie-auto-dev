import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.issue.IssueManager;
import com.atlassian.jira.project.ProjectManager;

import javax.ws.rs.GET;
import javax.ws.rs.Path;
import javax.ws.rs.Produces;
import javax.ws.rs.core.MediaType;
import java.util.List;

@Path("/jira")
@Produces(MediaType.APPLICATION_JSON)
public class JiraService {

    private final Jira jira;
    private final IssueManager issueManager;
    private final ProjectManager projectManager;

    public JiraService(Jira jira, IssueManager issueManager, ProjectManager projectManager) {
        this.jira = jira;
        this.issueManager = issueManager;
        this.projectManager = projectManager;
    }

    @GET
    public List<Issue> getIssues() {
        return issueManager.getAllIssues();
    }

    @GET
    @Path("/projects")
    public List<Project> getProjects() {
        return projectManager.getAllProjects();
    }
}

import static org.junit.jupiter.api.Assertions.*;

public class JiraServiceTest {

    private JiraService jiraService;

    @BeforeEach
    public void setUp() {
        // Configuração do Jira e outros objetos necessários para o teste
        jiraService = new JiraService(/* instância de Jira */, /* instância de IssueManager */, /* instância de ProjectManager */);
    }

    @Test
    public void testGetIssuesSuccess() {
        List<Issue> issues = jiraService.getIssues();
        assertNotNull(issues, "List of issues should not be null");
        assertFalse(issues.isEmpty(), "List of issues should not be empty");
    }

    @Test
    public void testGetIssuesFailure() {
        // Simula um erro de divisão por zero
        try {
            jiraService.getIssues();
            fail("Expected an exception to be thrown");
        } catch (ArithmeticException e) {
            assertEquals("Cannot divide by zero", e.getMessage(), "Error message should match expected");
        }
    }

    @Test
    public void testGetProjectsSuccess() {
        List<Project> projects = jiraService.getProjects();
        assertNotNull(projects, "List of projects should not be null");
        assertFalse(projects.isEmpty(), "List of projects should not be empty");
    }

    @Test
    public void testGetProjectsFailure() {
        // Simula um erro de divisão por zero
        try {
            jiraService.getProjects();
            fail("Expected an exception to be thrown");
        } catch (ArithmeticException e) {
            assertEquals("Cannot divide by zero", e.getMessage(), "Error message should match expected");
        }
    }

    @AfterEach
    public void tearDown() {
        // Limpeza de recursos após o teste
    }
}