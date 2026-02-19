import com.atlassian.jira.client.JiraClient;
import com.atlassian.jira.client.JiraClientBuilder;
import com.atlassian.jira.client.api.model.Issue;

public class JavaAgentJiraIntegration {

    private static final String JIRA_URL = "http://your-jira-server.com";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    public static void main(String[] args) {
        try (JiraClient client = new JiraClientBuilder(JIRA_URL)
                .setUsername(USERNAME)
                . setPassword(PASSWORD)
                .build()) {

            // Example: Create a new issue
            Issue issue = createIssue(client, "My New Issue", "This is a test issue.");

            System.out.println("Issue created successfully: " + issue.getKey());
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    private static Issue createIssue(JiraClient client, String summary, String description) throws Exception {
        return client.createIssue(summary, description);
    }
}