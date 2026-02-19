import com.atlassian.jira.client.api.JiraClient;
import com.atlassian.jira.client.api.JiraClientBuilder;
import com.atlassian.jira.client.api.domain.Issue;
import com.atlassian.jira.client.api.domain.User;

import java.io.IOException;
import java.util.List;

public class JavaAgent {

    private JiraClient jiraClient;

    public JavaAgent(String jiraUrl, String username, String password) {
        this.jiraClient = new JiraClientBuilder(jiraUrl)
                .username(username)
                .password(password)
                .build();
    }

    public void logActivity(String issueKey, String activityDescription) throws IOException {
        Issue issue = jiraClient.getIssue(issueKey);
        User reporter = issue.getReporter();

        System.out.println("Logging activity for issue " + issueKey + ": " + activityDescription);

        // Simulate logging to a file or database
        // For simplicity, we'll just print the log to the console
        System.out.println("Logged by: " + reporter.getName());
    }

    public static void main(String[] args) {
        JavaAgent agent = new JavaAgent("https://your-jira-instance.atlassian.net", "username", "password");

        try {
            agent.logActivity("ABC-123", "This is a test log activity.");
        } catch (IOException e) {
            e.printStackTrace();
        }
    }
}