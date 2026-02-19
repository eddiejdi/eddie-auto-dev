import com.atlassian.jira.client.api.JiraClient;
import com.atlassian.jira.client.api.JiraClientBuilder;
import com.atlassian.jira.client.api.domain.Issue;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;

public class JiraIntegrationTest {

    private JiraClient jiraClient;

    @BeforeEach
    public void setUp() {
        jiraClient = new JiraClientBuilder("https://your-jira-instance.com")
                .setUsername("your-username")
                . setPassword("your-password")
                .build();
    }

    @Test
    public void testCreateIssue() throws Exception {
        Issue issue = jiraClient.createIssue("My New Issue", "This is a test issue.");
        assertEquals(issue.getKey(), "MYNEWISSUE");
        assertEquals(issue.getSummary(), "My New Issue: This is a test issue.");
    }

    @Test
    public void testUpdateIssue() throws Exception {
        Issue issue = jiraClient.createIssue("My New Issue", "This is a test issue.");
        Issue updatedIssue = jiraClient.updateIssue(issue.getId(), "Updated issue title");
        assertEquals(updatedIssue.getKey(), "MYNEWISSUE");
        assertEquals(updatedIssue.getSummary(), "Updated issue title: This is a test issue.");
    }

    @Test
    public void testDeleteIssue() throws Exception {
        Issue issue = jiraClient.createIssue("My New Issue", "This is a test issue.");
        boolean deleted = jiraClient.deleteIssue(issue.getId());
        assertTrue(deleted);
    }

    @Test
    public void testCreateIssueWithInvalidKey() throws Exception {
        assertThrows(IllegalArgumentException.class, () -> jiraClient.createIssue(null, "This is a test issue."));
    }

    @Test
    public void testUpdateIssueWithInvalidKey() throws Exception {
        Issue issue = jiraClient.createIssue("My New Issue", "This is a test issue.");
        assertThrows(IllegalArgumentException.class, () -> jiraClient.updateIssue(null, "Updated issue title"));
    }

    @Test
    public void testDeleteIssueWithInvalidId() throws Exception {
        assertThrows(IllegalArgumentException.class, () -> jiraClient.deleteIssue(0));
    }
}