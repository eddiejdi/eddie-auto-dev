import com.atlassian.jira.client.api.JiraClient;
import com.atlassian.jira.client.api.JiraClientBuilder;
import com.atlassian.jira.client.api.domain.BasicIssue;
import com.atlassian.jira.client.api.domain.Issue;
import com.atlassian.jira.client.api.domain.WorklogEntry;

import java.io.IOException;
import java.util.List;

public class JavaAgent {

    private static final String JIRA_URL = "https://your-jira-instance.com";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    public static void main(String[] args) {
        try (JiraClient client = new JiraClientBuilder(JIRA_URL).login(USERNAME, PASSWORD).build()) {

            // Create a new issue
            BasicIssue issue = new BasicIssue();
            issue.setProjectKey("YOUR_PROJECT_KEY");
            issue.setSummary("Test Issue");
            issue.setDescription("This is a test issue created by the Java Agent.");
            issue.setStatus("OPEN");

            Issue createdIssue = client.createIssue(issue);
            System.out.println("Created issue: " + createdIssue.getKey());

            // Add worklog to the issue
            WorklogEntry worklogEntry = new WorklogEntry();
            worklogEntry.setAuthor("JavaAgent");
            worklogEntry.setDate(new java.util.Date());
            worklogEntry.setDescription("This is a test worklog entry added by the Java Agent.");

            client.addWorklog(createdIssue.getKey(), worklogEntry);
            System.out.println("Worklog added to issue: " + createdIssue.getKey());

        } catch (IOException e) {
            e.printStackTrace();
        }
    }
}