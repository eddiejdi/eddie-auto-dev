import com.atlassian.jira.client.api.JiraClient;
import com.atlassian.jira.client.api.JiraClientBuilder;
import com.atlassian.jira.client.api.domain.Issue;
import com.atlassian.jira.client.api.domain.User;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;

public class JavaAgentJiraIntegrationTest {

    private static final String JIRA_URL = "https://your-jira-instance.com";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    private JiraClient client;

    @BeforeEach
    public void setUp() {
        try (JiraClientBuilder builder = new JiraClientBuilder(JIRA_URL)
                .setUsername(USERNAME)
                . setPassword(PASSWORD)) {
            client = builder.build();
        }
    }

    @Test
    public void testCreateIssueSuccess() throws Exception {
        String projectKey = "SCRUM-13";
        String summary = "Bug report";

        Issue issue = createIssue(client, projectKey, summary);

        assertNotNull(issue);
        assertEquals(projectKey, issue.getProjectKey());
        assertEquals(summary, issue.getSummary());
    }

    @Test
    public void testCreateIssueFailureDivideByZero() throws Exception {
        String projectKey = "SCRUM-13";
        String summary = "Bug report";

        try {
            createIssue(client, projectKey, "");
        } catch (Exception e) {
            assertEquals("Division by zero", e.getMessage());
        }
    }

    @Test
    public void testCreateIssueFailureInvalidSummary() throws Exception {
        String projectKey = "SCRUM-13";
        String summary = null;

        try {
            createIssue(client, projectKey, summary);
        } catch (Exception e) {
            assertEquals("Summary cannot be null", e.getMessage());
        }
    }

    private Issue createIssue(JiraClient client, String projectKey, String summary) throws Exception {
        // Create the issue object
        Issue issue = new Issue()
                .setProjectKey(projectKey)
                .setSummary(summary)
                .setDescription("This is a test description");

        // Create the issue in JIRA
        return client.getIssueManager().create(issue);
    }
}