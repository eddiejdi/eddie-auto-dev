import com.atlassian.jira.rest.client.api.JiraRestClient;
import com.atlassian.jira.rest.client.api.RestClientFactory;
import com.atlassian.jira.rest.client.auth.BasicHttpAuthenticationHandler;
import com.atlassian.jira.rest.client.model.Issue;
import com.atlassian.jira.rest.client.model.SearchRequest;
import com.atlassian.jira.rest.client.model.SearchResult;

import java.io.IOException;
import java.util.List;

public class JiraAgent {

    private static final String JIRA_URL = "https://your-jira-instance.com";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    public static void main(String[] args) {
        try (JiraRestClient client = RestClientFactory.create(JIRA_URL, new BasicHttpAuthenticationHandler(USERNAME, PASSWORD))) {

            // Search for issues
            SearchRequest searchRequest = new SearchRequest();
            searchRequest.setQuery("project=YOUR_PROJECT_KEY");
            SearchResult searchResult = client.searchIssue(searchRequest);

            List<Issue> issues = searchResult.getIssues();

            for (Issue issue : issues) {
                System.out.println("Issue ID: " + issue.getId());
                System.out.println("Summary: " + issue.getKey() + " - " + issue.getSummary());
                System.out.println("Status: " + issue.getStatus().getName());
                System.out.println("----------------------------------------");
            }

        } catch (IOException e) {
            e.printStackTrace();
        }
    }
}