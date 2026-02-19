import com.atlassian.jira.client.api.JiraClient;
import com.atlassian.jira.client.api.JiraClientBuilder;
import com.atlassian.jira.client.api.domain.Issue;
import com.atlassian.jira.client.api.domain.SearchResult;
import com.atlassian.jira.client.api.domain.WorklogEntry;

import java.io.IOException;
import java.util.List;

public class JavaAgentJiraIntegrator {

    private static final String JIRA_URL = "https://your-jira-instance.com";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    public static void main(String[] args) {
        try (JiraClient jiraClient = new JiraClientBuilder(JIRA_URL).setUsername(USERNAME). setPassword(PASSWORD).build()) {

            // Create a new issue
            Issue issue = createIssue(jiraClient, "Test Issue", "This is a test issue.");

            // Add a worklog entry to the issue
            addWorklogEntry(jiraClient, issue.getId(), "Completed task");

            // Search for issues
            SearchResult searchResult = searchIssues(jiraClient, "Test");
            List<Issue> issues = searchResult.getIssues();
            for (Issue i : issues) {
                System.out.println("Issue ID: " + i.getKey() + ", Summary: " + i.getSummary());
            }
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    private static Issue createIssue(JiraClient jiraClient, String key, String summary) throws IOException {
        return jiraClient.createIssue(key, summary);
    }

    private static void addWorklogEntry(JiraClient jiraClient, String issueId, String comment) throws IOException {
        WorklogEntry worklogEntry = jiraClient.addWorklog(issueId, comment);
        System.out.println("Worklog entry added: " + worklogEntry.getKey());
    }

    private static SearchResult searchIssues(JiraClient jiraClient, String query) throws IOException {
        return jiraClient.searchJql(query);
    }
}