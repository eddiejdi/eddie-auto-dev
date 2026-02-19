import com.atlassian.jira.client.api.JiraClient;
import com.atlassian.jira.client.api.JiraClientBuilder;
import com.atlassian.jira.client.api.domain.Issue;
import com.atlassian.jira.client.api.domain.Status;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

import java.util.NoSuchElementException;

public class JiraIntegrationServiceTest {

    @Test
    public void testLogActivitySuccess() {
        // Arrange
        JiraClientBuilder builder = Mockito.mock(JiraClientBuilder.class);
        JiraClient client = Mockito.mock(JiraClient.class);
        Issue issue = Mockito.mock(Issue.class);
        Status status = Mockito.mock(Status.class);

        try (Mockito.when(builder.build()).thenReturn(client)) {
            Mockito.when(client.getIssueClient().getIssue("YOUR-ISSUE-ID")).thenReturn(issue);
            Mockito.when(issue.getStatus()).thenReturn(status);
            Mockito.when(client.getIssueClient().updateIssue(issue.getId(), "IN_PROGRESS")).thenReturn(null);
        }

        JiraIntegrationService service = new JiraIntegrationService();
        service.logActivity("Processing task...");

        // Assert
        Mockito.verify(client).getIssueClient().getIssue("YOUR-ISSUE-ID");
        Mockito.verify(client.getIssueClient()).updateIssue(issue.getId(), "IN_PROGRESS");
    }

    @Test
    public void testLogActivityFailure() {
        // Arrange
        JiraClientBuilder builder = Mockito.mock(JiraClientBuilder.class);
        JiraClient client = Mockito.mock(JiraClient.class);
        Issue issue = Mockito.mock(Issue.class);

        try (Mockito.when(builder.build()).thenReturn(client)) {
            Mockito.when(client.getIssueClient().getIssue("YOUR-ISSUE-ID")).thenThrow(new NoSuchElementException());
        }

        JiraIntegrationService service = new JiraIntegrationService();
        service.logActivity("Processing task...");

        // Assert
        Mockito.verify(client).getIssueClient().getIssue("YOUR-ISSUE-ID");
    }
}