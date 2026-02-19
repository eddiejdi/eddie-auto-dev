import com.atlassian.jira.rest.client.api.JiraRestClient;
import com.atlassian.jira.rest.client.api.RestClientBuilder;
import com.atlassian.jira.rest.client.api.domain.Issue;
import com.atlassian.jira.rest.client.api.domain.Project;
import com.atlassian.jira.rest.client.api.domain.User;
import com.atlassian.jira.rest.client.auth.BasicHttpAuthenticationHandler;

import java.io.IOException;
import java.util.List;

public class JavaAgent {

    private static final String JIRA_URL = "https://your-jira-instance.com";
    private static final String USERNAME = "your-username";
    private static final String PASSWORD = "your-password";

    public static void main(String[] args) {
        try (JiraRestClient client = new RestClientBuilder()
                .setServerURI(JIRA_URL)
                .addAuthHandler(new BasicHttpAuthenticationHandler(USERNAME, PASSWORD))
                .build()) {

            Project project = client.getProjectClient().getProject("YOUR-PROJECT-ID");
            System.out.println("Project: " + project.getName());

            User user = client.getUserClient().getUser("YOUR-USER-ID");
            System.out.println("User: " + user.getName());

            List<Issue> issues = client.getIssueClient().searchIssues("project=YOUR-PROJECT-ID AND status!=closed", 0, 10);
            for (Issue issue : issues) {
                System.out.println("Issue: " + issue.getKey() + ", Status: " + issue.getStatus());
            }

        } catch (IOException e) {
            e.printStackTrace();
        }
    }
}