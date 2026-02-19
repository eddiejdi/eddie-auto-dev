import com.atlassian.jira.client.JiraClient;
import com.atlassian.jira.client.JiraClientBuilder;
import com.atlassian.jira.client.api.IssueService;
import com.atlassian.jira.client.api.dto.issue.Issue;
import com.atlassian.jira.client.api.dto.search.SearchResult;
import com.atlassian.jira.client.auth.BasicHttpAuthenticationHandler;

import java.io.IOException;
import java.util.List;

public class JavaAgentJiraIntegrator {

    private static final String JIRA_URL = "https://your-jira-instance.com";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    public static void main(String[] args) {
        try (JiraClient client = new JiraClientBuilder(JIRA_URL)
                .setAuthenticationHandler(new BasicHttpAuthenticationHandler(USERNAME, PASSWORD))
                .build()) {

            IssueService issueService = client.getIssueService();

            // Example: Search for issues
            SearchResult searchResult = issueService.search("project=YOUR_PROJECT", null);
            List<Issue> issues = searchResult.getIssues();

            for (Issue issue : issues) {
                System.out.println("Issue ID: " + issue.getId());
                System.out.println("Summary: " + issue.getKey() + " - " + issue.getSummary());
            }

        } catch (IOException e) {
            e.printStackTrace();
        }
    }
}