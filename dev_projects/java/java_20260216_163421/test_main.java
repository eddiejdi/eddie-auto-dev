import com.atlassian.jira.ComponentManager;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.IssueManager;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.project.ProjectManager;

public class JavaAgentJiraIntegrationTest {

    private ComponentManager componentManager;
    private IssueManager issueManager;
    private ProjectManager projectManager;

    @Before
    public void setUp() {
        // Inicializa o JIRA ComponentManager
        componentManager = ComponentManager.getInstance();

        // Obtém a IssueManager e ProjectManager
        issueManager = componentManager.getComponent(IssueManager.class);
        projectManager = componentManager.getComponent(ProjectManager.class);
    }

    @Test
    public void testGetIssueById() {
        long issueId = 12345L;
        try {
            Issue issue = issueManager.getIssue(issueId);
            assertNotNull(issue, "Issue should not be null");
            assertEquals("issue-key", issue.getKey(), "Key should match expected value");
        } catch (Exception e) {
            fail("Error retrieving issue: " + e.getMessage());
        }
    }

    @Test
    public void testGetIssuesByProject() {
        try {
            Project project = projectManager.getProjectByKey("PROJECT_KEY");
            assertNotNull(project, "Project should not be null");
            List<Issue> issues = project.getIssues();
            assertNotNull(issues, "Issues list should not be null");
            assertFalse(issues.isEmpty(), "There should be at least one issue in the project");
        } catch (Exception e) {
            fail("Error retrieving issues from project: " + e.getMessage());
        }
    }

    @Test
    public void testCreateIssue() {
        try {
            Project project = projectManager.getProjectByKey("PROJECT_KEY");
            Issue newIssue = issueManager.createIssue(project, "New Test Issue", "This is a test issue.");
            assertNotNull(newIssue, "New issue should not be null");
            assertEquals("new-test-issue-key", newIssue.getKey(), "Key should match expected value");
        } catch (Exception e) {
            fail("Error creating issue: " + e.getMessage());
        }
    }

    @Test
    public void testCreateIssueWithInvalidData() {
        try {
            Project project = projectManager.getProjectByKey("PROJECT_KEY");
            Issue newIssue = issueManager.createIssue(project, null, "This is a test issue.");
            assertNull(newIssue, "New issue should be null");
        } catch (Exception e) {
            fail("Error creating issue with invalid data: " + e.getMessage());
        }
    }

    @After
    public void tearDown() {
        // Limpeza após os testes
    }
}