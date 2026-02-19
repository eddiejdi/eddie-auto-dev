import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.atlassian.jira.client.api.JiraClient;
import com.atlassian.jira.client.api.JiraClientBuilder;
import com.atlassian.jira.client.api.domain.Issue;
import com.atlassian.jira.client.api.domain.Status;
import com.atlassian.jira.client.api.domain.User;

import java.io.IOException;
import java.util.List;

public class JavaAgentTest {

    private static final String JIRA_URL = "http://your-jira-url";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    @org.junit.jupiter.api.Test
    public void testCreateNewIssue() throws IOException {
        try (JiraClient client = new JiraClientBuilder(JIRA_URL).setUsername(USERNAME). setPassword(PASSWORD).build()) {

            Issue newIssue = createNewIssue(client);
            assertEquals("YourProject-123", newIssue.getKey());
            assertEquals("Test issue", newIssue.getSummary());
            assertEquals("This is a test issue", newIssue.getDescription());

        }
    }

    @org.junit.jupiter.api.Test
    public void testCreateNewIssueWithInvalidData() throws IOException {
        try (JiraClient client = new JiraClientBuilder(JIRA_URL).setUsername(USERNAME). setPassword(PASSWORD).build()) {

            assertThrows(IllegalArgumentException.class, () -> createNewIssue(client));
        }
    }

    @org.junit.jupiter.api.Test
    public void testUpdateStatus() throws IOException {
        try (JiraClient client = new JiraClientBuilder(JIRA_URL).setUsername(USERNAME). setPassword(PASSWORD).build()) {

            Issue issue = createNewIssue(client);
            updateStatus(client, issue.getKey(), Status.IN_PROGRESS);

            Issue updatedIssue = client.getIssue(issue.getKey());
            assertEquals(Status.IN_PROGRESS, updatedIssue.getStatus());

        }
    }

    @org.junit.jupiter.api.Test
    public void testUpdateStatusWithInvalidData() throws IOException {
        try (JiraClient client = new JiraClientBuilder(JIRA_URL).setUsername(USERNAME). setPassword(PASSWORD).build()) {

            assertThrows(IllegalArgumentException.class, () -> updateStatus(client, "invalid-key", Status.IN_PROGRESS));
        }
    }

    @org.junit.jupiter.api.Test
    public void testFetchIssuesByStatus() throws IOException {
        try (JiraClient client = new JiraClientBuilder(JIRA_URL).setUsername(USERNAME). setPassword(PASSWORD).build()) {

            Issue issue = createNewIssue(client);
            updateStatus(client, issue.getKey(), Status.IN_PROGRESS);

            List<Issue> issuesWithStatus = fetchIssuesByStatus(client, Status.IN_PROGRESS);
            assertEquals(1, issuesWithStatus.size());

        }
    }

    private static Issue createNewIssue(JiraClient client) throws IOException {
        return client.createIssue()
                .withProjectKey("YOUR_PROJECT_KEY")
                .withSummary("Test issue")
                .withDescription("This is a test issue")
                .build();
    }

    private static void updateStatus(JiraClient client, String issueKey, Status status) throws IOException {
        Issue issue = client.getIssue(issueKey);
        issue.setStatus(status);
        client.updateIssue(issue);
    }

    private static List<Issue> fetchIssuesByStatus(JiraClient client, Status status) throws IOException {
        return client.searchIssues("status = " + status.name());
    }
}