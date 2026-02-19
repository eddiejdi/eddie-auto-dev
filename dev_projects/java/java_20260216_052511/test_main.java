import com.atlassian.jira.client.api.JiraClient;
import com.atlassian.jira.client.api.JiraClientBuilder;
import com.atlassian.jira.client.api.domain.Issue;
import com.atlassian.jira.client.api.domain.User;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Value;

import java.util.Optional;

public class JiraServiceTest {

    @Value("${jira.url}")
    private String jiraUrl;

    @Value("${jira.username}")
    private String username;

    @Value("${jira.password}")
    private String password;

    private JiraClient client;
    private Issue issue;
    private User user;

    @BeforeEach
    public void setUp() {
        try (JiraClientBuilder builder = new JiraClientBuilder(jiraUrl)
                .username(username)
                .password(password)
                .build()) {

            client = builder.build();
            issue = client.getIssue("ABC-123");
            user = client.getUser(client.getCurrentUser().getName());
        } catch (Exception e) {
            System.err.println("Error setting up JiraClient: " + e.getMessage());
        }
    }

    @Test
    public void testTrackActivitySuccess() {
        String activity = "User logged in";
        trackActivity(issue.getKey(), activity);

        // Add assertions to verify that the activity was tracked correctly
        // For example:
        // assert issue.getFields().get("customfield_12345").getValue().equals(activity);
    }

    @Test
    public void testTrackActivityError() {
        String activity = "Invalid activity";
        trackActivity(issue.getKey(), activity);

        // Add assertions to verify that an error was thrown when tracking the activity
        // For example:
        // assert exception.getMessage().contains("Invalid activity");
    }
}