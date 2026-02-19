import com.atlassian.jira.client.api.JiraClient;
import com.atlassian.jira.client.api.JiraClientBuilder;
import com.atlassian.jira.client.api.domain.Issue;
import com.atlassian.jira.client.api.domain.SearchResult;
import com.atlassian.jira.client.api.domain.WorklogEntry;

import java.io.IOException;
import java.util.List;

public class JavaAgentJiraIntegratorTest {

    private static final String JIRA_URL = "https://your-jira-instance.com";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    public void testCreateIssue() throws IOException {
        try (JiraClient jiraClient = new JiraClientBuilder(JIRA_URL).setUsername(USERNAME). setPassword(PASSWORD).build()) {
            Issue issue = createIssue(jiraClient, "Test Issue", "This is a test issue.");
            assert issue.getKey().equals("TEST-1");
            assert issue.getSummary().equals("Test Issue");
        }
    }

    public void testAddWorklogEntry() throws IOException {
        try (JiraClient jiraClient = new JiraClientBuilder(JIRA_URL).setUsername(USERNAME). setPassword(PASSWORD).build()) {
            Issue issue = createIssue(jiraClient, "Test Issue", "This is a test issue.");
            addWorklogEntry(jiraClient, issue.getId(), "Completed task");
            WorklogEntry worklogEntry = jiraClient.getWorklog(issue.getId());
            assert worklogEntry.getKey().equals("TEST-1-WL1");
        }
    }

    public void testSearchIssues() throws IOException {
        try (JiraClient jiraClient = new JiraClientBuilder(JIRA_URL).setUsername(USERNAME). setPassword(PASSWORD).build()) {
            SearchResult searchResult = searchIssues(jiraClient, "Test");
            List<Issue> issues = searchResult.getIssues();
            assert !issues.isEmpty();
            for (Issue i : issues) {
                assert i.getKey().equals("TEST-1") || i.getKey().equals("TEST-2");
                assert i.getSummary().contains("Test");
            }
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