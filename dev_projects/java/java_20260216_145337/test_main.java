import com.atlassian.jira.client.api.JiraClient;
import com.atlassian.jira.client.api.JiraClientBuilder;
import com.atlassian.jira.client.api.auth.BasicHttpAuthenticationHandler;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Value;

import java.io.IOException;

public class JiraServiceTest {

    @Value("${jira.url}")
    private String jiraUrl;

    @Value("${jira.username}")
    private String username;

    @Value("${jira.password}")
    private String password;

    @Test
    public void testLogActivitySuccess() throws IOException {
        JiraService jiraService = new JiraService();
        jiraService.logActivity("New feature implemented");
    }

    @Test
    public void testLogActivityError() throws IOException {
        // Test case for error handling (e.g., invalid username/password)
        try {
            JiraService jiraService = new JiraService();
            jiraService.logActivity("Invalid credentials");
        } catch (IOException e) {
            // Expected exception
            assert e.getMessage().contains("Error logging activity");
        }
    }

    @Test
    public void testLogActivityEdgeCase() throws IOException {
        // Test case for edge cases (e.g., empty string)
        JiraService jiraService = new JiraService();
        jiraService.logActivity("");
    }
}