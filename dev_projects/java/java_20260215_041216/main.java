import com.atlassian.jira.client.api.JiraClient;
import com.atlassian.jira.client.api.JiraClientBuilder;
import com.atlassian.jira.client.api.JiraException;
import com.atlassian.jira.client.api.model.Issue;

public class JiraIntegration {

    private static final String JIRA_URL = "https://your-jira-instance.com";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    public static void main(String[] args) {
        try (JiraClient client = new JiraClientBuilder(JIRA_URL)
                .setUsername(USERNAME)
                . setPassword(PASSWORD)
                .build()) {

            // Create a new issue
            Issue issue = createIssue(client, "Test Issue", "This is a test issue.");

            System.out.println("Issue created: " + issue.getKey());
        } catch (JiraException e) {
            e.printStackTrace();
        }
    }

    private static Issue createIssue(JiraClient client, String summary, String description) throws JiraException {
        // Create an issue object
        Issue issue = new Issue()
                .setSummary(summary)
                .setDescription(description);

        // Create the issue in Jira
        return client.createIssue(issue);
    }
}