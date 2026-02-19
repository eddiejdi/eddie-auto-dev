import com.atlassian.jira.client.JiraClient;
import com.atlassian.jira.client.auth.BasicHttpAuthHandler;
import com.atlassian.jira.client.rest.RestClientFactory;
import com.atlassian.jira.client.rest.RestClientFactoryBuilder;
import com.atlassian.jira.client.rest.api.IssueService;
import com.atlassian.jira.client.rest.api.domain.BasicIssueInputParameters;
import com.atlassian.jira.client.rest.api.domain.IssueInputParameters;
import com.atlassian.jira.client.rest.api.domain.JiraException;

import java.io.IOException;

public class JavaAgentJiraIntegration {

    private static final String JIRA_URL = "https://your-jira-instance.com";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    public static void main(String[] args) {
        try {
            // Create a JiraClient instance
            RestClientFactory factory = new RestClientFactoryBuilder()
                    .setJiraUrl(JIRA_URL)
                    .build();
            JiraClient client = factory.create();

            // Authenticate with Jira
            BasicHttpAuthHandler authHandler = new BasicHttpAuthHandler(USERNAME, PASSWORD);
            client.setAuthentication(authHandler);

            // Create a new issue
            IssueInputParameters issueInput = new BasicIssueInputParameters()
                    .setProjectKey("YOUR_PROJECT_KEY")
                    .setSummary("New Java Agent Integration")
                    .setDescription("This is a test of integrating the Java Agent with Jira.");

            IssueService issueService = client.getIssueService();
            issueService.create(issueInput);

            System.out.println("Issue created successfully.");
        } catch (JiraException | IOException e) {
            e.printStackTrace();
        }
    }
}