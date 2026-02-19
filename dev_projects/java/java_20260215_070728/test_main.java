import com.atlassian.jira.client.JiraClient;
import com.atlassian.jira.client.auth.BasicHttpAuthenticationHandler;
import com.atlassian.jira.client.rest.RestClientFactory;
import com.atlassian.jira.client.rest.RestClientFactoryBuilder;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class JavaAgentIntegratorTest {

    private static final String JIRA_URL = "https://your-jira-instance.com";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    @Test
    public void testCreateJiraClient() throws Exception {
        try (JiraClient jiraClient = createJiraClient()) {
            assertNotNull(jiraClient);
        } catch (Exception e) {
            fail("Error creating Jira client: " + e.getMessage());
        }
    }

    private static JiraClient createJiraClient() throws Exception {
        RestClientFactory factory = new RestClientFactoryBuilder()
                .setBaseUrl(JIRA_URL)
                .addAuthHandler(new BasicHttpAuthenticationHandler(USERNAME, PASSWORD))
                .build();

        return factory.create();
    }
}