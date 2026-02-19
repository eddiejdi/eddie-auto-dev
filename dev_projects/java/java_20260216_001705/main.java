import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.TextField;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.project.ProjectManager;

import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

public class JavaAgentJiraIntegrator {

    private Jira jira;
    private Project project;
    private CustomFieldManager customFieldManager;
    private FieldManager fieldManager;

    public static void main(String[] args) {
        try {
            JavaAgentJiraIntegrator integrator = new JavaAgentJiraIntegrator();
            integrator.init();
            integrator.trackActivity("Task123", "Completed");
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    public void init() throws IOException {
        // Initialize Jira connection
        jira = new Jira();
        project = jira.getProjectManager().getProjectByKey("YOUR_PROJECT_KEY");
        customFieldManager = jira.getCustomFieldManager();
        fieldManager = jira.getFieldManager();

        // Create a text field for logging
        TextField logField = createTextField(project, "Log", "Log messages");

        // Set up the Java Agent Jira Integrator
        setupJavaAgentJiraIntegrator(logField);
    }

    public void trackActivity(String issueKey, String status) throws IOException {
        Issue issue = jira.getIssueManager().getIssue(issueKey);

        // Update the issue status
        updateIssueStatus(issue, status);

        // Log the activity
        logActivity("Updated status to " + status, issue);
    }

    private void createTextField(Project project, String name, String description) throws IOException {
        Field field = fieldManager.createField(name, description, "text", null);
        customFieldManager.saveCustomField(field);
        return (TextField) field;
    }

    private void setupJavaAgentJiraIntegrator(TextField logField) throws IOException {
        // Implement Java Agent Jira Integrator logic here
        System.out.println("Java Agent Jira Integrator initialized with log field: " + logField.getName());
    }

    private void updateIssueStatus(Issue issue, String status) throws IOException {
        issue.setStatus(status);
        jira.getIssueManager().updateIssue(issue, null);
        System.out.println("Issue status updated to " + status);
    }

    private void logActivity(String message, Issue issue) throws IOException {
        TextField logField = (TextField) customFieldManager.getFieldByName("Log");
        String logValue = issue.getCustomFieldValue(logField).toString();
        logValue += "\n" + message;
        issue.setCustomFieldValue(logField, logValue);
        jira.getIssueManager().updateIssue(issue, null);
        System.out.println("Activity logged: " + message);
    }
}