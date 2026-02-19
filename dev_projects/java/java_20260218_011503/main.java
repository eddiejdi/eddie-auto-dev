import com.atlassian.jira.rest.client.api.RestClientBuilder;
import com.atlassian.jira.rest.client.api.auth.BasicHttpAuthenticationHandler;
import com.atlassian.jira.rest.client.api.model.Issue;
import com.atlassian.jira.rest.client.api.model.IssueField;
import com.atlassian.jira.rest.client.api.model.IssueInputParameters;
import com.atlassian.jira.rest.client.api.model.IssueUpdateParameters;
import com.atlassian.jira.rest.client.api.model.Project;
import com.atlassian.jira.rest.client.api.model.User;

import java.io.IOException;
import java.util.List;
import java.util.Map;

public class JavaAgent {

    private static final String JIRA_URL = "https://your-jira-instance.com";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    public static void main(String[] args) {
        try (RestClientBuilder builder = new RestClientBuilder()) {
            builder.setEndpoint(JIRA_URL);
            builder.addAuthHandler(new BasicHttpAuthenticationHandler(USERNAME, PASSWORD));
            JavaAgent agent = new JavaAgent(builder.build());
            agent.registerEvent("Test Event", "This is a test event.");
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    public JavaAgent(RestClientBuilder clientBuilder) throws IOException {
        this.client = clientBuilder.build();
    }

    private final RestClient client;

    public void registerEvent(String summary, String description) throws IOException {
        Project project = getProject("Your Project Key");
        User user = getUser("Your Username");

        IssueInputParameters issueInputParams = new IssueInputParameters()
                .setSummary(summary)
                .setDescription(description);

        Issue issue = client.createIssue(project.getId(), user.getId(), issueInputParams);
        System.out.println("Event registered: " + issue.getKey());
    }

    private Project getProject(String projectKey) throws IOException {
        return client.getProjectClient().getProjectByKey(projectKey).claim();
    }

    private User getUser(String username) throws IOException {
        return client.getUserClient().getUser(username).claim();
    }
}