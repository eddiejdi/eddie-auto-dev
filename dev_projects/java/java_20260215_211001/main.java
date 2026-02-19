import com.atlassian.jira.client.api.JiraClient;
import com.atlassian.jira.client.api.JiraClientBuilder;
import com.atlassian.jira.client.api.domain.Issue;
import com.atlassian.jira.client.api.domain.Status;
import com.atlassian.jira.client.api.domain.User;

import java.io.IOException;
import java.util.List;

public class JavaAgent {

    private static final String JIRA_URL = "http://your-jira-url";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    public static void main(String[] args) {
        try (JiraClient client = new JiraClientBuilder(JIRA_URL).setUsername(USERNAME). setPassword(PASSWORD).build()) {

            // Create a new issue
            Issue newIssue = createNewIssue(client);
            System.out.println("Created issue: " + newIssue.getKey());

            // Update the status of an existing issue
            updateStatus(client, newIssue.getKey(), Status.IN_PROGRESS);

            // Fetch all issues with a specific status
            List<Issue> issuesWithStatus = fetchIssuesByStatus(client, Status.IN_PROGRESS);
            System.out.println("Issues with status IN_PROGRESS: " + issuesWithStatus.size());

        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    private static Issue createNewIssue(JiraClient client) throws IOException {
        // Create a new issue
        return client.createIssue()
                .withProjectKey("YOUR_PROJECT_KEY")
                .withSummary("Test issue")
                .withDescription("This is a test issue")
                .build();
    }

    private static void updateStatus(JiraClient client, String issueKey, Status status) throws IOException {
        // Update the status of an existing issue
        Issue issue = client.getIssue(issueKey);
        issue.setStatus(status);
        client.updateIssue(issue);
    }

    private static List<Issue> fetchIssuesByStatus(JiraClient client, Status status) throws IOException {
        // Fetch all issues with a specific status
        return client.searchIssues("status = " + status.name());
    }
}