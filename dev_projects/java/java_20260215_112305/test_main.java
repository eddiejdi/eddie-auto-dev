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

public class JavaAgentJiraIntegrationTest {

    private static final String JIRA_URL = "http://your-jira-server.com";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    @Test
    public void testCreateCustomField() throws IOException {
        try (JiraClient jiraClient = new JiraClientBuilder(JIRA_URL).setUsername(USERNAME). setPassword(PASSWORD).build()) {

            CustomFieldManager customFieldManager = jiraClient.getCustomFieldManager();
            String name = "Activity";
            Class<?> fieldType = TextField.class;

            CustomField activityField = createCustomField(customFieldManager, name, fieldType);

            assertNotNull(activityField);
            assertEquals(name, activityField.getName());
        }
    }

    @Test
    public void testCreateIssue() throws IOException {
        try (JiraClient jiraClient = new JiraClientBuilder(JIRA_URL).setUsername(USERNAME). setPassword(PASSWORD).build()) {

            Project project = jiraClient.getProjectManager().getProjectByKey("YOUR-PROJECT-KEY");

            String summary = "New Activity Tracking";
            Issue issue = createIssue(jiraClient, project.getKey(), summary);

            assertNotNull(issue);
            assertEquals(project.getKey(), issue.getProjectKey());
            assertEquals(summary, issue.getSummary());
        }
    }

    @Test
    public void testUpdateIssueWithCustomField() throws IOException {
        try (JiraClient jiraClient = new JiraClientBuilder(JIRA_URL).setUsername(USERNAME). setPassword(PASSWORD).build()) {

            Project project = jiraClient.getProjectManager().getProjectByKey("YOUR-PROJECT-KEY");

            String summary = "New Activity Tracking";
            Issue issue = createIssue(jiraClient, project.getKey(), summary);

            long customFieldId = getCustomFieldId(jiraClient, "Activity");
            String value = "Task completed";

            updateIssueWithCustomField(jiraClient, issue.getId(), customFieldId, value);

            Issue updatedIssue = jiraClient.getIssueManager().getIssue(issue.getId());
            assertEquals(value, updatedIssue.getField(customFieldId).getValueAsString());
        }
    }

    private static CustomField createCustomField(CustomFieldManager customFieldManager, String name, Class<?> fieldType) throws IOException {
        return customFieldManager.createCustomField(name, fieldType);
    }

    private static Issue createIssue(JiraClient jiraClient, String projectKey, String summary) throws IOException {
        return jiraClient.getIssueManager().createIssue(project.getKey(), summary);
    }

    private static void updateIssueWithCustomField(JiraClient jiraClient, String issueId, long customFieldId, String value) throws IOException {
        FieldManager fieldManager = jiraClient.getFieldManager();
        CustomField activityField = fieldManager.getCustomField(customFieldId);

        Issue issue = jiraClient.getIssueManager().getIssue(issueId);
        issue.update(fieldManager.getField(activityField), value);
    }

    private static long getCustomFieldId(JiraClient jiraClient, String name) throws IOException {
        CustomFieldManager customFieldManager = jiraClient.getCustomFieldManager();
        List<CustomField> customFields = customFieldManager.getAllCustomFields();

        for (CustomField field : customFields) {
            if (field.getName().equals(name)) {
                return field.getId();
            }
        }

        throw new RuntimeException("Custom field not found");
    }
}