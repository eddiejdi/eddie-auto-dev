import com.atlassian.jira.client.api.JiraClient;
import com.atlassian.jira.client.api.JiraClientBuilder;
import com.atlassian.jira.client.api.domain.Issue;
import com.atlassian.jira.client.api.domain.User;

import java.io.IOException;
import java.util.List;

public class JavaAgentTest {

    private JavaAgent agent;

    @Before
    public void setUp() {
        this.agent = new JavaAgent("https://your-jira-instance.atlassian.net", "username", "password");
    }

    @After
    public void tearDown() {
        // Clean up resources if necessary
    }

    @Test
    public void testLogActivitySuccess() throws IOException {
        String issueKey = "ABC-123";
        String activityDescription = "This is a test log activity.";

        agent.logActivity(issueKey, activityDescription);

        // Assert that the log was printed to the console
        // This can be done using assertions like System.out.println captured by a mock or logging framework
    }

    @Test(expected = IOException.class)
    public void testLogActivityFailure() throws IOException {
        String issueKey = "ABC-123";
        String activityDescription = "";

        agent.logActivity(issueKey, activityDescription);
    }
}