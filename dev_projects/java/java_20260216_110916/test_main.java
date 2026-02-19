import com.atlassian.jira.client.api.JiraClient;
import com.atlassian.jira.client.api.JiraClientBuilder;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.io.IOException;

public class JiraAgentTest {

    private static final String JIRA_URL = "https://your-jira-instance.com";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    private JiraClient jiraClient;

    @BeforeEach
    public void setUp() {
        try (JiraClientBuilder builder = new JiraClientBuilder(JIRA_URL).setUsername(USERNAME). setPassword(PASSWORD)) {
            jiraClient = builder.build();
        } catch (IOException e) {
            throw new RuntimeException("Failed to create Jira client", e);
        }
    }

    @Test
    public void testJiraAgentInitialization() {
        assertNotNull(jiraClient, "Jira client should not be null");
    }

    // Add more tests here...
}