import com.atlassian.jira.client.JiraClient;
import com.atlassian.jira.client.auth.BasicHttpAuthenticationHandler;
import com.atlassian.jira.client.rest.RestClientBuilder;

public class JavaAgentJiraIntegration {

    private static final String JIRA_URL = "http://your-jira-server.com";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    public static void main(String[] args) {
        try (JiraClient client = RestClientBuilder.newBuilder()
                .setServerUrl(JIRA_URL)
                .setAuthenticationHandler(new BasicHttpAuthenticationHandler(USERNAME, PASSWORD))
                .build()) {

            // Example: Create a new issue
            String issueKey = "TEST-1";
            String summary = "Test Issue";

            // Create the issue object
            com.atlassian.jira.client.api.model.Issue issue = client.createIssue(issueKey, summary);

            System.out.println("Created issue: " + issue.getKey());

        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}