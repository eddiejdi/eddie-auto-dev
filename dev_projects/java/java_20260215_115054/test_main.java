import com.atlassian.jira.client.api.JiraClient;
import com.atlassian.jira.client.api.JiraClientBuilder;
import com.atlassian.jira.client.api.domain.BasicIssue;
import com.atlassian.jira.client.api.domain.IssueField;
import com.atlassian.jira.client.api.domain.IssueType;
import com.atlassian.jira.client.api.domain.WorklogEntry;

import java.util.List;

public class JavaAgentJiraIntegrationTest {

    private static final String JIRA_URL = "https://your-jira-instance.atlassian.net";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    @Test
    public void testCreateNewIssue() throws Exception {
        try (JiraClient client = new JiraClientBuilder(JIRA_URL)
                .setUsername(USERNAME)
                . setPassword(PASSWORD)
                .build()) {

            BasicIssue newIssue = createNewIssue(client);

            assertNotNull(newIssue);
            assertEquals("Create a new issue", newIssue.getSummary());
            assertEquals("This is a test issue", newIssue.getDescription());
        }
    }

    @Test
    public void testLogWork() throws Exception {
        try (JiraClient client = new JiraClientBuilder(JIRA_URL)
                .setUsername(USERNAME)
                . setPassword(PASSWORD)
                .build()) {

            BasicIssue newIssue = createNewIssue(client);
            String issueKey = newIssue.getKey();

            logWork(client, issueKey);

            // Additional assertions can be added here to verify the worklog entry was created
        }
    }

    @Test
    public void testUpdateIssueWithMetricsAndLogs() throws Exception {
        try (JiraClient client = new JiraClientBuilder(JIRA_URL)
                .setUsername(USERNAME)
                . setPassword(PASSWORD)
                .build()) {

            BasicIssue newIssue = createNewIssue(client);
            String issueKey = newIssue.getKey();

            updateIssueWithMetricsAndLogs(client, issueKey);

            // Additional assertions can be added here to verify the issue was updated with metrics and logs
        }
    }

    private static BasicIssue createNewIssue(JiraClient client) throws Exception {
        IssueField summary = client.getFields().getByName("summary");
        IssueField description = client.getFields().getByName("description");

        BasicIssue issue = new BasicIssue()
                .setSummary(summary.getValue("Create a new issue"))
                .setDescription(description.getValue("This is a test issue"));

        return client.createIssue(issue);
    }

    private static void logWork(JiraClient client, String issueKey) throws Exception {
        WorklogEntry worklogEntry = new WorklogEntry()
                .setAuthor(client.getUser().getName())
                .setComment("Logged some work")
                .setStartDate(System.currentTimeMillis());

        client.addWorklog(issueKey, worklogEntry);
    }

    private static void updateIssueWithMetricsAndLogs(JiraClient client, String issueKey) throws Exception {
        // Example of updating metrics and logs
        IssueField customField1 = client.getFields().getByName("customfield_12345"); // Replace with your custom field key
        IssueField customField2 = client.getFields().getByName("customfield_67890"); // Replace with your custom field key

        BasicIssue issue = client.getIssue(issueKey);

        issue.setCustomFieldValue(customField1, "Metric value");
        issue.setCustomFieldValue(customField2, "Log entry");

        client.updateIssue(issue);
    }
}