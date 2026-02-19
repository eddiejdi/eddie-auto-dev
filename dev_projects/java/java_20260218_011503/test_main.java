import com.atlassian.jira.rest.client.api.RestClientBuilder;
import com.atlassian.jira.rest.client.api.auth.BasicHttpAuthenticationHandler;
import com.atlassian.jira.rest.client.api.model.Issue;
import com.atlassian.jira.rest.client.api.model.IssueField;
import com.atlassian.jira.rest.client.api.model.IssueInputParameters;
import com.atlassian.jira.rest.client.api.model.IssueUpdateParameters;
import com.atlassian.jira.rest.client.api.model.Project;
import com.atlassian.jira.rest.client.api.model.User;

import java.io.IOException;

public class JavaAgentTest {

    private static final String JIRA_URL = "https://your-jira-instance.com";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    public void testRegisterEventWithValidData() throws IOException {
        RestClientBuilder builder = new RestClientBuilder();
        builder.setEndpoint(JIRA_URL);
        builder.addAuthHandler(new BasicHttpAuthenticationHandler(USERNAME, PASSWORD));
        JavaAgent agent = new JavaAgent(builder.build());

        Project project = getProject("Your Project Key");
        User user = getUser("Your Username");

        IssueInputParameters issueInputParams = new IssueInputParameters()
                .setSummary("Test Event")
                .setDescription("This is a test event.");

        agent.registerEvent(issueInputParams);
    }

    public void testRegisterEventWithInvalidData() throws IOException {
        RestClientBuilder builder = new RestClientBuilder();
        builder.setEndpoint(JIRA_URL);
        builder.addAuthHandler(new BasicHttpAuthenticationHandler(USERNAME, PASSWORD));
        JavaAgent agent = new JavaAgent(builder.build());

        Project project = getProject("Your Project Key");
        User user = getUser("Your Username");

        IssueInputParameters issueInputParams = new IssueInputParameters()
                .setSummary(null)
                .setDescription("");

        try {
            agent.registerEvent(issueInputParams);
            fail("Expected an IOException to be thrown");
        } catch (IOException e) {
            // Expected behavior
        }
    }

    private Project getProject(String projectKey) throws IOException {
        return client.getProjectClient().getProjectByKey(projectKey).claim();
    }

    private User getUser(String username) throws IOException {
        return client.getUserClient().getUser(username).claim();
    }
}