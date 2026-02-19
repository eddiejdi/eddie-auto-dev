import com.atlassian.jira.rest.client.api.RestClientBuilder;
import com.atlassian.jira.rest.client.api.auth.BasicHttpAuthenticationHandler;
import com.atlassian.jira.rest.client.api.model.Issue;
import com.atlassian.jira.rest.client.api.model.SearchResult;

import java.io.IOException;
import java.util.List;

public class JiraScrum13 {

    private static final String JIRA_URL = "https://your-jira-instance.com";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    public static void main(String[] args) {
        try (RestClientBuilder builder = new RestClientBuilder()) {
            builder.setEndpoint(JIRA_URL);
            builder.addAuthHandler(new BasicHttpAuthenticationHandler(USERNAME, PASSWORD));

            JiraScrum13 jiraScrum13 = new JiraScrum13();
            jiraScrum13.trackActivity("Issue-123");
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    public void trackActivity(String issueKey) throws IOException {
        RestClientBuilder builder = new RestClientBuilder();
        builder.setEndpoint(JIRA_URL);
        builder.addAuthHandler(new BasicHttpAuthenticationHandler(USERNAME, PASSWORD));

        JiraScrum13 jiraScrum13 = new JiraScrum13();
        Issue issue = jiraScrum13.getIssue(issueKey);

        if (issue != null) {
            System.out.println("Tracking activity for issue: " + issue.getKey());
            // Add code to monitor and manage tickets
        } else {
            System.out.println("Issue not found: " + issueKey);
        }
    }

    private Issue getIssue(String issueKey) throws IOException {
        RestClientBuilder builder = new RestClientBuilder();
        builder.setEndpoint(JIRA_URL);
        builder.addAuthHandler(new BasicHttpAuthenticationHandler(USERNAME, PASSWORD));

        JiraScrum13 jiraScrum13 = new JiraScrum13();
        return jiraScrum13.searchIssues("key=" + issueKey).getResults().get(0);
    }
}