import com.atlassian.jira.client.api.JiraClient;
import com.atlassian.jira.client.api.JiraClientBuilder;
import com.atlassian.jira.client.api.exception.RestException;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.CustomField;
import com.atlassian.jira.issue.fields.TextField;

import java.io.IOException;
import java.util.List;

public class JavaAgentJiraIntegration {

    private static final String JIRA_URL = "http://your-jira-server.com";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    public static void main(String[] args) {
        try (JiraClient jiraClient = new JiraClientBuilder(JIRA_URL).setUsername(USERNAME). setPassword(PASSWORD).build()) {

            // Get the project
            Project project = jiraClient.getProjectManager().getProjectByKey("YOUR-PROJECT-KEY");

            // Create a custom field for tracking activities
            CustomFieldManager customFieldManager = jiraClient.getCustomFieldManager();
            CustomField activityField = createCustomField(customFieldManager, "Activity", TextField.class);

            // Create an issue and set the custom field value
            Issue issue = createIssue(jiraClient, project.getKey(), "New Activity Tracking");
            updateIssueWithCustomField(jiraClient, issue.getId(), activityField.getId(), "Task completed");

        } catch (RestException | IOException e) {
            e.printStackTrace();
        }
    }

    private static CustomField createCustomField(CustomFieldManager customFieldManager, String name, Class<?> fieldType) throws IOException {
        CustomField customField = customFieldManager.createCustomField(name, fieldType);
        return customField;
    }

    private static Issue createIssue(JiraClient jiraClient, String projectKey, String summary) throws IOException {
        Project project = jiraClient.getProjectManager().getProjectByKey(projectKey);
        Issue issue = jiraClient.getIssueManager().createIssue(project.getKey(), summary);
        return issue;
    }

    private static void updateIssueWithCustomField(JiraClient jiraClient, String issueId, long customFieldId, String value) throws IOException {
        FieldManager fieldManager = jiraClient.getFieldManager();
        CustomField activityField = fieldManager.getCustomField(customFieldId);

        Issue issue = jiraClient.getIssueManager().getIssue(issueId);
        issue.update(fieldManager.getField(activityField), value);
    }
}