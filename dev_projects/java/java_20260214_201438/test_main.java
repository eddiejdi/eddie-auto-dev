import com.atlassian.jira.client.api.JiraClient;
import com.atlassian.jira.client.api.JiraClientBuilder;
import com.atlassian.jira.client.api.domain.Issue;
import com.atlassian.jira.client.api.domain.SearchResults;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Value;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

public class JiraServiceTest {

    @Value("${jira.url}")
    private String jiraUrl;

    @Value("${jira.username}")
    private String username;

    @Value("${jira.password}")
    private String password;

    private JiraClient client;
    private Update update;

    @BeforeEach
    public void setUp() {
        try (JiraClientBuilder builder = new JiraClientBuilder(jiraUrl)
                .username(username)
                .password(password)
                .build()) {

            client = builder.build();
            update = new Update("New activity");
        } catch (Exception e) {
            System.err.println("Error setting up: " + e.getMessage());
        }
    }

    @Test
    public void testTrackActivitySuccess() {
        try {
            client.issueService().update("ABC-123", update);
            assertEquals("New activity", client.issueService().getIssue("ABC-123").getDescription());
        } catch (Exception e) {
            System.err.println("Error tracking activity: " + e.getMessage());
        }
    }

    @Test
    public void testTrackActivityFailure() {
        assertThrows(Exception.class, () -> client.issueService().update("XYZ-456", update));
    }

    @Test
    public void testTrackActivityInvalidIssueKey() {
        assertThrows(Exception.class, () -> client.issueService().update("INVALID-ISSUE", update));
    }
}