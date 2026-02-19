import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.UserPickerField;
import com.atlassian.jira.issue.fields.TextField;
import com.atlassian.jira.user.User;

public class JiraIntegration {

    private static final String JIRA_URL = "http://your-jira-url";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    public static void main(String[] args) {
        try {
            // Initialize Jira service context
            JiraServiceContext jiraServiceContext = new JiraServiceContext(JIRA_URL, USERNAME, PASSWORD);

            // Get Jira instance
            Jira jira = new Jira(jiraServiceContext);

            // Create a new project
            Project project = createProject(jira);
            System.out.println("Project created: " + project.getName());

            // Create a new issue
            Issue issue = createIssue(jira, project.getId());
            System.out.println("Issue created: " + issue.getKey());

            // Add custom field value to the issue
            addCustomFieldValue(issue, jira);

            // Close the issue
            closeIssue(jira, issue);
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    private static Project createProject(Jira jira) throws Exception {
        Project project = jira.createProject("My Project", "My Project Description");
        return project;
    }

    private static Issue createIssue(Jira jira, long projectId) throws Exception {
        Issue issue = jira.createIssue(projectId, "My Issue", "This is a test issue.");
        return issue;
    }

    private static void addCustomFieldValue(Issue issue, Jira jira) throws Exception {
        FieldManager fieldManager = jira.getFieldManager();
        CustomFieldManager customFieldManager = jira.getCustomFieldManager();

        // Create a user picker field
        UserPickerField userPickerField = (UserPickerField) customFieldManager.getCustomFieldObjectByName("Assignee");

        // Create a text field
        TextField textField = (TextField) customFieldManager.getCustomFieldObjectByName("Description");

        // Get the current user
        User currentUser = jira.getJiraAuthenticationContext().getUser();

        // Add values to the issue
        issue.setFieldValue(userPickerField, currentUser);
        issue.setFieldValue(textField, "This is a test description.");

        // Update the issue
        jira.updateIssue(issue);
    }

    private static void closeIssue(Jira jira, Issue issue) throws Exception {
        issue.setStatus("Closed");
        jira.updateIssue(issue);
    }
}