import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.IssueManager;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.project.ProjectManager;
import com.atlassian.jira.service.ServiceContext;
import com.atlassian.jira.web.action.JiraActionSupport;

public class JavaAgentJiraIntegrationTest {

    private static final long serialVersionUID = 1L;

    private IssueManager issueManager;
    private ProjectManager projectManager;

    @Before
    public void setUp() {
        this.issueManager = ComponentAccessor.getComponent(IssueManager.class);
        this.projectManager = ComponentAccessor.getComponent(ProjectManager.class);
    }

    @Test
    public void testCreateIssueWithValidData() throws Exception {
        ServiceContext serviceContext = ComponentAccessor.getOSGiComponentInstanceOfType(ServiceContext.class);
        Project project = projectManager.getProjectByKey("YOUR_PROJECT_KEY"); // Substitua pela chave do projeto em Jira

        Issue issue = issueManager.createIssue(serviceContext, project, "Task", "Implement Java Agent integration with Jira");
        assertNotNull(issue);
    }

    @Test(expected = IllegalArgumentException.class)
    public void testCreateIssueWithInvalidData() throws Exception {
        ServiceContext serviceContext = ComponentAccessor.getOSGiComponentInstanceOfType(ServiceContext.class);
        Project project = projectManager.getProjectByKey("YOUR_PROJECT_KEY"); // Substitua pela chave do projeto em Jira

        issueManager.createIssue(serviceContext, project, "Task", "");
    }

    @Test
    public void testUpdateProjectWithValidData() throws Exception {
        ServiceContext serviceContext = ComponentAccessor.getOSGiComponentInstanceOfType(ServiceContext.class);
        Project project = projectManager.getProjectByKey("YOUR_PROJECT_KEY"); // Substitua pela chave do projeto em Jira

        issueManager.updateProject(project, true);
    }

    @Test(expected = IllegalArgumentException.class)
    public void testUpdateProjectWithInvalidData() throws Exception {
        ServiceContext serviceContext = ComponentAccessor.getOSGiComponentInstanceOfType(ServiceContext.class);
        Project project = projectManager.getProjectByKey("YOUR_PROJECT_KEY"); // Substitua pela chave do projeto em Jira

        issueManager.updateProject(project, false);
    }
}