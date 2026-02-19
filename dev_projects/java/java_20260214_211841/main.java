import com.atlassian.jira.client.api.JiraClient;
import com.atlassian.jira.client.api.JiraClientBuilder;
import com.atlassian.jira.client.api.domain.Issue;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

@Component
public class JiraIntegration implements CommandLineRunner {

    private static final String JIRA_URL = "https://your-jira-instance.com";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    @Override
    public void run(String... args) throws Exception {
        JiraClient jiraClient = new JiraClientBuilder(JIRA_URL)
                .setUsername(USERNAME)
                . setPassword(PASSWORD)
                .build();

        // Example: Create a new issue
        Issue issue = jiraClient.createIssue("My New Issue", "This is a test issue.");
        System.out.println("Created issue ID: " + issue.getId());

        // Example: Update an existing issue
        Issue updatedIssue = jiraClient.updateIssue(issue.getId(), "Updated issue title");
        System.out.println("Updated issue title: " + updatedIssue.getKey() + ": " + updatedIssue.getSummary());

        // Example: Delete an issue
        boolean deleted = jiraClient.deleteIssue(issue.getId());
        if (deleted) {
            System.out.println("Deleted issue ID: " + issue.getId());
        } else {
            System.out.println("Failed to delete issue ID: " + issue.getId());
        }
    }
}