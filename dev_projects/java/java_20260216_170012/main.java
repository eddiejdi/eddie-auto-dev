import com.atlassian.jira.client.api.JiraClient;
import com.atlassian.jira.client.api.JiraClientBuilder;
import com.atlassian.jira.client.api.domain.Issue;
import com.atlassian.jira.client.api.domain.User;

public class JavaAgentJiraIntegration {

    private static final String JIRA_URL = "https://your-jira-instance.com";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    public static void main(String[] args) {
        try (JiraClient client = new JiraClientBuilder(JIRA_URL)
                .setUsername(USERNAME)
                . setPassword(PASSWORD)
                .build()) {

            // Get the current user
            User currentUser = client.getUserManager().getUserByName(client.getAuthentication().getLoggedInUser());

            // Create a new issue
            Issue issue = createIssue(client, "Bug", "This is a bug report");

            System.out.println("Created issue: " + issue.getKey());
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    private static Issue createIssue(JiraClient client, String projectKey, String summary) throws Exception {
        // Create the issue object
        Issue issue = new Issue()
                .setProjectKey(projectKey)
                .setSummary(summary)
                .setDescription("This is a test description");

        // Create the issue in JIRA
        return client.getIssueManager().create(issue);
    }
}