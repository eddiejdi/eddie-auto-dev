import com.atlassian.jira.client.api.JiraClient;
import com.atlassian.jira.client.api.JiraClients;
import com.atlassian.jira.client.api.domain.Issue;
import com.atlassian.jira.client.api.domain.input.IssueInput;
import com.atlassian.jira.client.api.exception.JiraException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;

public class JiraIntegrationServiceTest {

    private JiraClient jiraClient;

    @BeforeEach
    public void setUp() {
        this.jiraClient = JiraClients.create("https://your-jira-instance.com", "your-username", "your-password");
    }

    @Test
    public void testCreateIssueWithValidInput() throws JiraException {
        String projectKey = "SCRUM-13";
        String issueType = "Task";
        String summary = "Implement feature X";

        Issue createdIssue = jiraClient.createIssue(new IssueInput()
                .setProject(projectKey)
                .setType(issueType)
                .setSummary(summary));

        assertNotNull(createdIssue);
    }

    @Test
    public void testCreateIssueWithInvalidInput() throws JiraException {
        String projectKey = "SCRUM-13";
        String issueType = "Task";
        String summary = "";

        assertThrows(JiraException.class, () -> jiraClient.createIssue(new IssueInput()
                .setProject(projectKey)
                .setType(issueType)
                .setSummary(summary)));
    }

    @Test
    public void testUpdateIssueWithValidInput() throws JiraException {
        String issueId = "12345";
        String summary = "Implement feature Y";

        jiraClient.updateIssue(new IssueInput()
                .setId(issueId)
                .setSummary(summary));

        assertNotNull(jiraClient.getIssue(issueId));
    }

    @Test
    public void testUpdateIssueWithInvalidInput() throws JiraException {
        String issueId = "12345";
        String summary = "";

        assertThrows(JiraException.class, () -> jiraClient.updateIssue(new IssueInput()
                .setId(issueId)
                .setSummary(summary)));
    }

    @Test
    public void testDeleteIssueWithValidInput() throws JiraException {
        String issueId = "12345";

        jiraClient.deleteIssue(issueId);

        assertNull(jiraClient.getIssue(issueId));
    }
}