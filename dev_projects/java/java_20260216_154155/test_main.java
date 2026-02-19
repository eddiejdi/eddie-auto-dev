import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.atlassian.jira.client.JiraClient;
import com.atlassian.jira.client.auth.BasicHttpAuthenticationHandler;
import com.atlassian.jira.client.domain.Issue;
import com.atlassian.jira.client.service.IssueService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

public class JavaAgentTest {

    private JiraClient jiraClient;
    private IssueService issueService;

    @BeforeEach
    public void setUp() {
        BasicHttpAuthenticationHandler authHandler = new BasicHttpAuthenticationHandler("your-username", "your-password");
        this.jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", authHandler);
        this.issueService = jiraClient.getIssueService();
    }

    @Test
    public void testCreateIssue() throws Exception {
        String issueKey = "TEST-123";
        String summary = "Test Issue";
        String description = "This is a test issue.";

        issueService.create(issueKey, summary, description);
        assertEquals("TEST-123", issue.getKey());
    }

    @Test
    public void testCreateIssueWithInvalidData() throws Exception {
        String issueKey = "TEST-123";
        String summary = "";
        String description = "This is a test issue.";

        assertThrows(IllegalArgumentException.class, () -> issueService.create(issueKey, summary, description));
    }

    @Test
    public void testUpdateIssue() throws Exception {
        String issueKey = "TEST-123";
        String summary = "Updated Test Issue";
        String description = "This is an updated test issue.";

        issueService.update(issueKey, summary, description);
        assertEquals("UPDATED TEST ISSUE", issue.getDescription());
    }

    @Test
    public void testUpdateIssueWithInvalidData() throws Exception {
        String issueKey = "TEST-123";
        String summary = "";
        String description = "This is a test issue.";

        assertThrows(IllegalArgumentException.class, () -> issueService.update(issueKey, summary, description));
    }

    @Test
    public void testDeleteIssue() throws Exception {
        String issueKey = "TEST-123";

        issueService.delete(issueKey);
    }

    @Test
    public void testDeleteIssueWithInvalidData() throws Exception {
        assertThrows(IllegalArgumentException.class, () -> issueService.delete("INVALID-KEY"));
    }
}