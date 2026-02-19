import com.atlassian.jira.client.api.JiraClient;
import com.atlassian.jira.client.api.JiraClientBuilder;
import com.atlassian.jira.client.api.domain.BasicIssue;
import com.atlassian.jira.client.api.domain.IssueField;
import com.atlassian.jira.client.api.domain.IssueType;
import com.atlassian.jira.client.api.domain.WorklogEntry;

import java.util.List;

public class JavaAgentJiraIntegration {

    private static final String JIRA_URL = "https://your-jira-instance.atlassian.net";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    public static void main(String[] args) {
        try (JiraClient client = new JiraClientBuilder(JIRA_URL)
                .setUsername(USERNAME)
                . setPassword(PASSWORD)
                .build()) {

            // Create a new issue
            BasicIssue newIssue = createNewIssue(client);

            // Log some work
            logWork(client, newIssue.getKey());

            // Update the issue with metrics and logs
            updateIssueWithMetricsAndLogs(client, newIssue.getKey());
        } catch (Exception e) {
            e.printStackTrace();
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