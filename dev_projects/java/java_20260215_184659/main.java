import com.atlassian.jira.client.JiraClient;
import com.atlassian.jira.client.JiraClientBuilder;
import com.atlassian.jira.model.Issue;

public class JavaAgentJiraIntegration {

    private static final String JIRA_URL = "https://your-jira-instance.com";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    public static void main(String[] args) {
        try (JiraClient client = new JiraClientBuilder(JIRA_URL)
                .setUsername(USERNAME)
                . setPassword(PASSWORD)
                .build()) {

            // Example issue creation
            Issue issue = client.createIssue("Test Issue", "This is a test issue.");
            System.out.println("Created issue: " + issue.getKey());

        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}