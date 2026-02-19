import com.atlassian.jira.client.api.JiraClient;
import com.atlassian.jira.client.api.JiraClientBuilder;
import com.atlassian.jira.client.api.domain.Issue;
import com.atlassian.jira.client.api.domain.IssueField;
import com.atlassian.jira.client.api.domain.IssueType;
import com.atlassian.jira.client.api.domain.User;
import com.atlassian.jira.rest.client.auth.BasicHttpAuthenticationHandler;

public class JavaAgent {

    private static final String JIRA_URL = "https://your-jira-instance.com";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    public static void main(String[] args) {
        // Create a Jira client
        JiraClient jiraClient = new JiraClientBuilder(JIRA_URL)
                .setAuthenticationHandler(new BasicHttpAuthenticationHandler(USERNAME, PASSWORD))
                .build();

        // Get the user who is running this script
        User currentUser = jiraClient.getUserManager().getMyself();
        System.out.println("Running as: " + currentUser.getName());

        // Create a new issue
        Issue issue = createIssue(jiraClient);
        System.out.println("Created issue: " + issue.getKey());

        // Close the Jira client
        try {
            jiraClient.close();
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    private static Issue createIssue(JiraClient jiraClient) {
        try {
            IssueType issueType = jiraClient.getIssueTypeManager().getIssueTypeByName("Bug");
            User reporter = jiraClient.getUserManager().getUserByUserName("reporter");

            Issue newIssue = jiraClient.createIssue(
                    "New Bug",
                    issueType,
                    reporter,
                    "This is a test bug."
            );

            return newIssue;
        } catch (Exception e) {
            e.printStackTrace();
            throw new RuntimeException("Failed to create issue", e);
        }
    }
}