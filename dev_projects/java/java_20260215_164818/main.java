import com.atlassian.jira.rest.client.api.RestClient;
import com.atlassian.jira.rest.client.api.RestClientBuilder;
import com.atlassian.jira.rest.client.auth.BasicHttpAuthenticationHandler;
import com.atlassian.jira.rest.client.domain.Issue;
import com.atlassian.jira.rest.client.domain.SearchResult;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class JiraService {

    @Autowired
    private RestClient restClient;

    public void connectToJira() {
        BasicHttpAuthenticationHandler authHandler = new BasicHttpAuthenticationHandler("username", "password");
        restClient = new RestClientBuilder()
                .setEndpoint("https://your-jira-instance.atlassian.net")
                .addAuthHandler(authHandler)
                .build();
    }

    public void searchIssues(String query) {
        SearchResult result = restClient.search(query);
        List<Issue> issues = result.getIssues();
        for (Issue issue : issues) {
            System.out.println("Issue ID: " + issue.getId());
            System.out.println("Summary: " + issue.getSummary());
        }
    }

    public void logEvent(String event) {
        restClient.createEvent(event);
        System.out.println("Event logged successfully");
    }

    public static void main(String[] args) {
        JiraService jiraService = new JiraService();
        jiraService.connectToJira();
        jiraService.searchIssues("your-jql-query");
        jiraService.logEvent("New issue created");
    }
}