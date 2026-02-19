import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.UserPickerField;
import com.atlassian.jira.issue.fields.TextField;
import com.atlassian.jira.user.User;

import static org.junit.jupiter.api.Assertions.*;

public class JiraIntegrationTest {

    private static final String JIRA_URL = "http://your-jira-url";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    @BeforeEach
    public void setUp() {
        // Initialize Jira service context
        JiraServiceContext jiraServiceContext = new JiraServiceContext(JIRA_URL, USERNAME, PASSWORD);

        // Get Jira instance
        Jira jira = new Jira(jiraServiceContext);
    }

    @Test
    public void testCreateProject() throws Exception {
        Project project = createProject(jira);
        assertNotNull(project);
        assertEquals("My Project", project.getName());
        assertEquals("My Project Description", project.getDescription());
    }

    @Test
    public void testCreateIssue() throws Exception {
        Project project = createProject(jira);
        Issue issue = createIssue(jira, project.getId());
        assertNotNull(issue);
        assertEquals("My Issue", issue.getKey());
        assertEquals("This is a test issue.", issue.getDescription());
    }

    @Test
    public void testAddCustomFieldValue() throws Exception {
        Project project = createProject(jira);
        Issue issue = createIssue(jira, project.getId());

        FieldManager fieldManager = jira.getFieldManager();
        CustomFieldManager customFieldManager = jira.getCustomFieldManager();

        UserPickerField userPickerField = (UserPickerField) customFieldManager.getCustomFieldObjectByName("Assignee");
        TextField textField = (TextField) customFieldManager.getCustomFieldObjectByName("Description");

        User currentUser = jira.getJiraAuthenticationContext().getUser();
        issue.setFieldValue(userPickerField, currentUser);
        issue.setFieldValue(textField, "This is a test description.");

        jira.updateIssue(issue);

        // Check if the field values were added correctly
        assertEquals(currentUser.getName(), issue.getFieldValue(userPickerField));
        assertEquals("This is a test description.", issue.getFieldValue(textField));
    }

    @Test
    public void testCloseIssue() throws Exception {
        Project project = createProject(jira);
        Issue issue = createIssue(jira, project.getId());

        issue.setStatus("Closed");
        jira.updateIssue(issue);

        // Check if the issue status was updated correctly
        assertEquals("Closed", issue.getStatus().getName());
    }

    private static Project createProject(Jira jira) throws Exception {
        return jira.createProject("My Project", "My Project Description");
    }

    private static Issue createIssue(Jira jira, long projectId) throws Exception {
        return jira.createIssue(projectId, "My Issue", "This is a test issue.");
    }
}