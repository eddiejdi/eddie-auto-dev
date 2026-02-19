import com.atlassian.jira.rest.client.api.RestClient;
import com.atlassian.jira.rest.client.api.RestClientBuilder;
import com.atlassian.jira.rest.client.auth.BasicHttpAuthenticationHandler;
import com.atlassian.jira.rest.client.domain.Issue;
import com.atlassian.jira.rest.client.domain.SearchResult;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class JiraServiceTest {

    @Autowired
    private RestClient restClient;

    @BeforeEach
    public void setUp() {
        BasicHttpAuthenticationHandler authHandler = new BasicHttpAuthenticationHandler("username", "password");
        restClient = new RestClientBuilder()
                .setEndpoint("https://your-jira-instance.atlassian.net")
                .addAuthHandler(authHandler)
                .build();
    }

    @Test
    public void testConnectToJira() {
        try {
            restClient.connect();
            System.out.println("Connected to Jira successfully");
        } catch (Exception e) {
            System.err.println("Failed to connect to Jira: " + e.getMessage());
        }
    }

    @Test
    public void testSearchIssues() {
        String query = "your-jql-query";
        try {
            SearchResult result = restClient.search(query);
            List<Issue> issues = result.getIssues();
            for (Issue issue : issues) {
                System.out.println("Issue ID: " + issue.getId());
                System.out.println("Summary: " + issue.getSummary());
            }
        } catch (Exception e) {
            System.err.println("Failed to search issues: " + e.getMessage());
        }
    }

    @Test
    public void testLogEvent() {
        String event = "New issue created";
        try {
            restClient.createEvent(event);
            System.out.println("Event logged successfully");
        } catch (Exception e) {
            System.err.println("Failed to log event: " + e.getMessage());
        }
    }

    @Test
    public void testSearchIssuesWithInvalidQuery() {
        String query = "";
        try {
            SearchResult result = restClient.search(query);
            List<Issue> issues = result.getIssues();
            for (Issue issue : issues) {
                System.out.println("Issue ID: " + issue.getId());
                System.out.println("Summary: " + issue.getSummary());
            }
        } catch (Exception e) {
            System.err.println("Failed to search issues with invalid query: " + e.getMessage());
        }
    }

    @Test
    public void testLogEventWithNullArgument() {
        try {
            restClient.createEvent(null);
            System.out.println("Event logged successfully");
        } catch (Exception e) {
            System.err.println("Failed to log event with null argument: " + e.getMessage());
        }
    }
}