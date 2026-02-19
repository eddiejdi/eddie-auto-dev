import com.atlassian.jira.api.JiraRestClient;
import com.atlassian.jira.rest.client.auth.BasicHttpAuthenticator;
import com.atlassian.jira.rest.client.invoker.ApiClient;

import javax.ws.rs.core.MediaType;
import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

public class JavaAgentJiraIntegrator {

    private static final String JIRA_URL = "http://your-jira-url";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    public static void main(String[] args) {
        try (ApiClient client = new ApiClient()) {
            BasicHttpAuthenticator authenticator = new BasicHttpAuthenticator(USERNAME, PASSWORD);
            client.setHttpClient(authenticator);

            JiraRestClient restClient = new JiraRestClient(client, JIRA_URL);

            Map<String, String> issueFields = new HashMap<>();
            issueFields.put("summary", "Test Java Agent Integration");
            issueFields.put("description", "Java Agent is integrated with Jira for tracking activities.");

            // Create an issue
            restClient.getIssueResource().create(issueFields);
        } catch (IOException e) {
            e.printStackTrace();
        }
    }
}